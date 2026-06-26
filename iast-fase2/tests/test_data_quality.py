"""
Testes de Qualidade de Dados
Valida as três camadas: Bronze, Silver e Gold.
Execute com: python tests/test_data_quality.py
"""

import os
import sys
import boto3
import pandas as pd
from io import BytesIO

S3_BUCKET = os.environ.get("S3_BUCKET", "iast-fase2-datalake")

CHECKS_PASSED = 0
CHECKS_FAILED = 0


def check(nome: str, condicao: bool, detalhe: str = ""):
    global CHECKS_PASSED, CHECKS_FAILED
    status = "✅ PASS" if condicao else "❌ FAIL"
    msg = f"  {status} | {nome}"
    if detalhe:
        msg += f"\n         → {detalhe}"
    print(msg)
    if condicao:
        CHECKS_PASSED += 1
    else:
        CHECKS_FAILED += 1


def read_parquet_s3(s3_client, prefix: str) -> pd.DataFrame:
    paginator = s3_client.get_paginator("list_objects_v2")
    dfs = []
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                body = s3_client.get_object(Bucket=S3_BUCKET, Key=obj["Key"])["Body"].read()
                dfs.append(pd.read_parquet(BytesIO(body)))
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


# ─── Testes Silver ───────────────────────────────────────────────────────────

def test_silver(s3):
    print("\n📋 Silver Layer:")
    df = read_parquet_s3(s3, "silver/inep/")

    check("Silver não está vazia", not df.empty, f"{len(df)} linhas")

    if df.empty:
        return

    # Sem duplicatas
    if "co_municipio" in df.columns and "ano" in df.columns:
        dups = df.duplicated(subset=["co_municipio", "ano"]).sum()
        check("Sem duplicatas (co_municipio + ano)", dups == 0, f"{dups} duplicata(s)")

    # Código IBGE válido
    if "co_municipio" in df.columns:
        invalidos = (~df["co_municipio"].astype(str).str.match(r"^\d{7}$")).sum()
        check("Código IBGE com 7 dígitos", invalidos == 0, f"{invalidos} inválido(s)")

    # Sem nulos em colunas críticas
    for col in ["co_municipio", "ano", "taxa_alfabetizacao"]:
        if col in df.columns:
            nulos = df[col].isnull().sum()
            check(f"Sem nulos em '{col}'", nulos == 0, f"{nulos} nulo(s)")

    # Taxa entre 0 e 100
    if "taxa_alfabetizacao" in df.columns:
        fora = ((df["taxa_alfabetizacao"] < 0) | (df["taxa_alfabetizacao"] > 100)).sum()
        check("taxa_alfabetizacao entre 0 e 100", fora == 0, f"{fora} valor(es) fora do intervalo")

    # Meta entre 0 e 100
    if "meta_alfabetizacao" in df.columns:
        fora = ((df["meta_alfabetizacao"] < 0) | (df["meta_alfabetizacao"] > 100)).sum()
        check("meta_alfabetizacao entre 0 e 100", fora == 0, f"{fora} valor(es) fora do intervalo")


# ─── Testes Gold ─────────────────────────────────────────────────────────────

def test_gold(s3):
    print("\n🏆 Gold Layer:")

    datasets_esperados = [
        "indicador_municipio_ano",
        "evolucao_temporal_uf",
        "comparacao_meta_resultado",
        "ranking_municipios",
    ]

    for ds in datasets_esperados:
        df = read_parquet_s3(s3, f"gold/{ds}/")
        check(f"Dataset '{ds}' existe e não está vazio", not df.empty, f"{len(df)} linhas")

    # Ranking: todos os municípios têm ranking
    df_rank = read_parquet_s3(s3, "gold/ranking_municipios/")
    if not df_rank.empty and "ranking_nacional" in df_rank.columns:
        sem_rank = df_rank["ranking_nacional"].isnull().sum()
        check("Todos municípios têm ranking_nacional", sem_rank == 0, f"{sem_rank} sem ranking")

    # Evolução temporal: pelo menos 2 anos
    df_evo = read_parquet_s3(s3, "gold/evolucao_temporal_uf/")
    if not df_evo.empty and "ano" in df_evo.columns:
        anos = df_evo["ano"].nunique()
        check("Evolução temporal com >= 2 anos", anos >= 2, f"{anos} ano(s) disponível(is)")


# ─── Testes Bronze ───────────────────────────────────────────────────────────

def test_bronze(s3):
    print("\n🟤 Bronze Layer:")

    paginator = s3_client.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix="bronze/inep/"):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith(".json"):
                keys.append(obj["Key"])

    check("Bronze possui arquivos", len(keys) > 0, f"{len(keys)} arquivo(s)")

    for key in keys[:3]:  # Valida os primeiros 3
        size = s3_client.head_object(Bucket=S3_BUCKET, Key=key)["ContentLength"]
        check(f"Arquivo não vazio: {key.split('/')[-1]}", size > 0, f"{size} bytes")


# ─── Relatório Final ─────────────────────────────────────────────────────────

def relatorio():
    total = CHECKS_PASSED + CHECKS_FAILED
    print("\n" + "=" * 60)
    print(f"RELATÓRIO DE QUALIDADE: {CHECKS_PASSED}/{total} checks passaram")
    if CHECKS_FAILED == 0:
        print("🎉 Todos os checks passaram!")
    else:
        print(f"⚠️  {CHECKS_FAILED} check(s) falharam — revise os dados.")
    print("=" * 60)
    return CHECKS_FAILED == 0


if __name__ == "__main__":
    print("=" * 60)
    print("VALIDAÇÃO DE QUALIDADE DE DADOS – IAST Fase 2")
    print("=" * 60)

    s3_client = boto3.client("s3")

    test_bronze(s3_client)
    test_silver(s3_client)
    test_gold(s3_client)

    ok = relatorio()
    sys.exit(0 if ok else 1)
