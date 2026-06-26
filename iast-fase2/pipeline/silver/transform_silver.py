"""
Silver Layer – Limpeza e Transformação
Lê dados brutos do S3 Bronze e aplica:
  - Remoção de duplicatas
  - Tratamento de valores ausentes
  - Padronização de nomes de colunas
  - Normalização de tipos
  - Validação de chaves (código IBGE do município)
  - Integração das duas bases (alfabetização + metas)
Salva resultado em Parquet particionado no S3 Silver.
"""

import os
import boto3
import pandas as pd
from io import BytesIO
from datetime import datetime, timezone

S3_BUCKET = os.environ.get("S3_BUCKET", "iast-fase2-datalake")
BRONZE_PREFIX = "bronze/inep/"
SILVER_PREFIX = "silver/inep/"


# ─── Leitura do S3 ────────────────────────────────────────────────────────────

def read_csv_from_s3(s3_client, key: str, **kwargs) -> pd.DataFrame:
    obj = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
    return pd.read_csv(BytesIO(obj["Body"].read()), **kwargs)


def list_s3_files(s3_client, prefix: str, suffix: str = ".csv") -> list:
    paginator = s3_client.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(suffix):
                keys.append(obj["Key"])
    return keys


# ─── Limpeza ─────────────────────────────────────────────────────────────────

def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza nomes de colunas: minúsculas, sem espaços, sem acentos."""
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace(r"[àáâãä]", "a", regex=True)
        .str.replace(r"[èéêë]", "e", regex=True)
        .str.replace(r"[ìíîï]", "i", regex=True)
        .str.replace(r"[òóôõö]", "o", regex=True)
        .str.replace(r"[ùúûü]", "u", regex=True)
        .str.replace(r"[ç]", "c", regex=True)
        .str.replace(r"[^a-z0-9_]", "_", regex=True)
    )
    return df


def remover_duplicatas(df: pd.DataFrame, chaves: list) -> pd.DataFrame:
    antes = len(df)
    df = df.drop_duplicates(subset=chaves, keep="last")
    removidos = antes - len(df)
    if removidos > 0:
        print(f"   ⚠️  {removidos} duplicata(s) removida(s) pela chave {chaves}")
    return df


def tratar_ausentes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Estratégia por tipo de coluna:
    - Numéricas: preenche com mediana do estado (UF)
    - Categóricas: preenche com 'NAO_INFORMADO'
    """
    num_cols = df.select_dtypes(include="number").columns
    cat_cols = df.select_dtypes(exclude="number").columns

    for col in num_cols:
        if df[col].isnull().any():
            if "uf" in df.columns:
                df[col] = df.groupby("uf")[col].transform(
                    lambda x: x.fillna(x.median())
                )
            df[col] = df[col].fillna(df[col].median())

    for col in cat_cols:
        df[col] = df[col].fillna("NAO_INFORMADO")

    return df


def validar_codigo_ibge(df: pd.DataFrame, col_municipio: str = "co_municipio") -> pd.DataFrame:
    """Valida que o código IBGE tem 7 dígitos e remove registros inválidos."""
    if col_municipio not in df.columns:
        print(f"   ℹ️  Coluna '{col_municipio}' não encontrada, pulando validação IBGE")
        return df

    df[col_municipio] = df[col_municipio].astype(str).str.strip()
    mask_valido = df[col_municipio].str.match(r"^\d{7}$")
    invalidos = (~mask_valido).sum()

    if invalidos > 0:
        print(f"   ⚠️  {invalidos} registro(s) com código IBGE inválido removido(s)")
        df = df[mask_valido].copy()

    return df


# ─── Transformações específicas ───────────────────────────────────────────────

def processar_indicador_alfabetizacao(df: pd.DataFrame) -> pd.DataFrame:
    df = padronizar_colunas(df)
    df = remover_duplicatas(df, chaves=["co_municipio", "ano"])
    df = tratar_ausentes(df)
    df = validar_codigo_ibge(df)

    # Garante tipos corretos
    if "ano" in df.columns:
        df["ano"] = df["ano"].astype(int)
    if "taxa_alfabetizacao" in df.columns:
        df["taxa_alfabetizacao"] = pd.to_numeric(df["taxa_alfabetizacao"], errors="coerce")

    df["processado_em"] = datetime.now(timezone.utc).isoformat()
    return df


def processar_metas_compromisso(df: pd.DataFrame) -> pd.DataFrame:
    df = padronizar_colunas(df)
    df = remover_duplicatas(df, chaves=["co_municipio", "ano"])
    df = tratar_ausentes(df)
    df = validar_codigo_ibge(df)

    if "meta_alfabetizacao" in df.columns:
        df["meta_alfabetizacao"] = pd.to_numeric(df["meta_alfabetizacao"], errors="coerce")

    df["processado_em"] = datetime.now(timezone.utc).isoformat()
    return df


def integrar_bases(df_indicador: pd.DataFrame, df_metas: pd.DataFrame) -> pd.DataFrame:
    """
    Integra indicador de alfabetização com metas municipais.
    Chave de join: co_municipio + ano
    """
    df_integrado = df_indicador.merge(
        df_metas,
        on=["co_municipio", "ano"],
        how="left",
        suffixes=("_indicador", "_meta"),
    )

    # Calcula diferença entre resultado e meta
    if "taxa_alfabetizacao" in df_integrado.columns and "meta_alfabetizacao" in df_integrado.columns:
        df_integrado["diferenca_meta"] = (
            df_integrado["taxa_alfabetizacao"] - df_integrado["meta_alfabetizacao"]
        )
        df_integrado["atingiu_meta"] = df_integrado["diferenca_meta"] >= 0

    return df_integrado


# ─── Escrita no S3 ────────────────────────────────────────────────────────────

def save_parquet_s3(df: pd.DataFrame, s3_client, prefix: str, partition_cols: list = None):
    """Salva DataFrame como Parquet no S3 Silver."""
    buffer = BytesIO()
    df.to_parquet(buffer, index=False, compression="snappy")
    buffer.seek(0)

    # Particionamento simples por ano e uf (se disponíveis)
    if partition_cols and all(c in df.columns for c in partition_cols):
        for keys, group in df.groupby(partition_cols):
            if not isinstance(keys, tuple):
                keys = (keys,)
            partition_path = "/".join(
                f"{col}={val}" for col, val in zip(partition_cols, keys)
            )
            buf = BytesIO()
            group.to_parquet(buf, index=False, compression="snappy")
            buf.seek(0)
            key = f"{prefix}{partition_path}/data.parquet"
            s3_client.put_object(Bucket=S3_BUCKET, Key=key, Body=buf.getvalue())
        print(f"   ✓ Salvo particionado em s3://{S3_BUCKET}/{prefix}")
    else:
        key = f"{prefix}data.parquet"
        s3_client.put_object(Bucket=S3_BUCKET, Key=key, Body=buffer.getvalue())
        print(f"   ✓ Salvo em s3://{S3_BUCKET}/{key}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    print("=" * 60)
    print("SILVER LAYER – Limpeza e Transformação")
    print("=" * 60)

    s3 = boto3.client("s3")

    # Lê arquivos Bronze
    bronze_keys = list_s3_files(s3, BRONZE_PREFIX)
    print(f"\n📂 {len(bronze_keys)} arquivo(s) encontrado(s) no Bronze")

    dfs_indicador = []
    dfs_metas = []

    for key in bronze_keys:
        print(f"\n📄 Processando: {key}")
        try:
            df = read_csv_from_s3(s3, key, encoding="latin-1", sep=";")

            if "indicador_alfabetizacao" in key:
                df = processar_indicador_alfabetizacao(df)
                dfs_indicador.append(df)
            elif "metas_compromisso" in key:
                df = processar_metas_compromisso(df)
                dfs_metas.append(df)
        except Exception as e:
            print(f"   ✗ Erro: {e}")

    # Consolida e integra
    if dfs_indicador and dfs_metas:
        df_ind = pd.concat(dfs_indicador, ignore_index=True)
        df_met = pd.concat(dfs_metas, ignore_index=True)
        df_silver = integrar_bases(df_ind, df_met)

        print(f"\n🔗 Integração: {len(df_silver)} registros")
        save_parquet_s3(
            df_silver, s3,
            prefix=f"{SILVER_PREFIX}alfabetizacao_integrado/",
            partition_cols=["ano", "uf"] if "uf" in df_silver.columns else None,
        )
    else:
        print("\n⚠️  Dados insuficientes para integração")

    print("\n✅ Silver Layer concluída!")


if __name__ == "__main__":
    run()
