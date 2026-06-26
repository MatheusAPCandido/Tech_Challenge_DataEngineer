"""
Gold Layer – Camada Analítica
Lê dados tratados do S3 Silver e produz datasets prontos para:
  - Dashboards
  - Análises estatísticas
  - Treinamento de modelos de ML

Datasets gerados:
  1. indicador_municipio_ano    – Índice de alfabetização por município e ano
  2. evolucao_temporal_uf       – Evolução por estado ao longo do tempo
  3. comparacao_meta_resultado  – Municípios que atingiram/não atingiram metas
  4. ranking_municipios         – Ranking do último ano disponível
"""

import os
import boto3
import pandas as pd
from io import BytesIO
from datetime import datetime, timezone

S3_BUCKET = os.environ.get("S3_BUCKET", "iast-fase2-datalake")
SILVER_PREFIX = "silver/inep/alfabetizacao_integrado/"
GOLD_PREFIX = "gold/"


# ─── Leitura ─────────────────────────────────────────────────────────────────

def read_parquet_from_s3(s3_client, prefix: str) -> pd.DataFrame:
    paginator = s3_client.get_paginator("list_objects_v2")
    dfs = []
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                body = s3_client.get_object(Bucket=S3_BUCKET, Key=obj["Key"])["Body"].read()
                dfs.append(pd.read_parquet(BytesIO(body)))

    if not dfs:
        raise FileNotFoundError(f"Nenhum Parquet encontrado em s3://{S3_BUCKET}/{prefix}")

    return pd.concat(dfs, ignore_index=True)


# ─── Datasets Gold ───────────────────────────────────────────────────────────

def build_indicador_municipio_ano(df: pd.DataFrame) -> pd.DataFrame:
    """
    Dataset 1: Indicador de alfabetização por município e ano.
    Granularidade: município × ano
    """
    cols = ["co_municipio", "no_municipio", "uf", "ano", "taxa_alfabetizacao",
            "meta_alfabetizacao", "diferenca_meta", "atingiu_meta"]
    cols_exist = [c for c in cols if c in df.columns]
    return df[cols_exist].copy()


def build_evolucao_temporal_uf(df: pd.DataFrame) -> pd.DataFrame:
    """
    Dataset 2: Evolução temporal da alfabetização por UF.
    Agregação: média ponderada por município dentro do estado.
    """
    if "uf" not in df.columns or "ano" not in df.columns:
        return pd.DataFrame()

    agg = (
        df.groupby(["uf", "ano"])
        .agg(
            taxa_media=("taxa_alfabetizacao", "mean"),
            taxa_minima=("taxa_alfabetizacao", "min"),
            taxa_maxima=("taxa_alfabetizacao", "max"),
            qtd_municipios=("co_municipio", "nunique"),
            municipios_na_meta=("atingiu_meta", "sum") if "atingiu_meta" in df.columns else ("co_municipio", "count"),
        )
        .reset_index()
    )
    agg["taxa_media"] = agg["taxa_media"].round(2)
    return agg


def build_comparacao_meta_resultado(df: pd.DataFrame) -> pd.DataFrame:
    """
    Dataset 3: Comparação entre metas e resultados por município.
    Permite identificar municípios em risco.
    """
    if "atingiu_meta" not in df.columns:
        return pd.DataFrame()

    ultimo_ano = df["ano"].max()
    df_ultimo = df[df["ano"] == ultimo_ano].copy()

    df_ultimo["status"] = df_ultimo["atingiu_meta"].map(
        {True: "META_ATINGIDA", False: "ABAIXO_DA_META"}
    ).fillna("SEM_META")

    cols = ["co_municipio", "no_municipio", "uf", "ano",
            "taxa_alfabetizacao", "meta_alfabetizacao", "diferenca_meta", "status"]
    cols_exist = [c for c in cols if c in df_ultimo.columns]
    return df_ultimo[cols_exist].sort_values("diferenca_meta")


def build_ranking_municipios(df: pd.DataFrame) -> pd.DataFrame:
    """
    Dataset 4: Ranking de municípios pelo índice de alfabetização.
    Útil para benchmarking e identificação de boas práticas.
    """
    if "taxa_alfabetizacao" not in df.columns:
        return pd.DataFrame()

    ultimo_ano = df["ano"].max()
    df_rank = df[df["ano"] == ultimo_ano].copy()
    df_rank["ranking_nacional"] = df_rank["taxa_alfabetizacao"].rank(
        ascending=False, method="min"
    ).astype(int)

    if "uf" in df_rank.columns:
        df_rank["ranking_estadual"] = df_rank.groupby("uf")["taxa_alfabetizacao"].rank(
            ascending=False, method="min"
        ).astype(int)

    return df_rank.sort_values("ranking_nacional")


# ─── Escrita ─────────────────────────────────────────────────────────────────

def save_gold_dataset(df: pd.DataFrame, name: str, s3_client):
    if df.empty:
        print(f"   ⚠️  Dataset '{name}' vazio, pulando")
        return

    buf = BytesIO()
    df.to_parquet(buf, index=False, compression="snappy")
    buf.seek(0)

    key = f"{GOLD_PREFIX}{name}/data.parquet"
    s3_client.put_object(Bucket=S3_BUCKET, Key=key, Body=buf.getvalue())
    print(f"   ✓ s3://{S3_BUCKET}/{key}  ({len(df)} linhas)")


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    print("=" * 60)
    print("GOLD LAYER – Datasets Analíticos")
    print("=" * 60)

    s3 = boto3.client("s3")

    print("\n📂 Lendo Silver Layer...")
    try:
        df = read_parquet_from_s3(s3, SILVER_PREFIX)
        print(f"   ✓ {len(df)} registros carregados")
    except FileNotFoundError as e:
        print(f"   ✗ {e}")
        print("   Execute primeiro: python pipeline/silver/transform_silver.py")
        return

    print("\n🏗️  Construindo datasets Gold:")

    datasets = {
        "indicador_municipio_ano":   build_indicador_municipio_ano(df),
        "evolucao_temporal_uf":      build_evolucao_temporal_uf(df),
        "comparacao_meta_resultado": build_comparacao_meta_resultado(df),
        "ranking_municipios":        build_ranking_municipios(df),
    }

    for name, dataset in datasets.items():
        print(f"\n📊 {name}")
        save_gold_dataset(dataset, name, s3)

    print("\n✅ Gold Layer concluída!")
    print(f"   Datasets disponíveis em: s3://{S3_BUCKET}/{GOLD_PREFIX}")
    print("   Consulte via AWS Athena apontando para esse caminho.")


if __name__ == "__main__":
    run()
