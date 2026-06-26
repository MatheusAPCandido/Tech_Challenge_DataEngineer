"""
Bronze Layer – Ingestão Raw
Lê os arquivos CSV/XLSX do INEP e salva no S3 sem transformações.
Registra metadados de ingestão (data, fonte, tamanho).
"""

import os
import json
import boto3
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

S3_BUCKET = os.environ.get("S3_BUCKET", "iast-fase2-datalake")
BRONZE_PREFIX = "bronze/inep/"


def list_bronze_files(local_dir: str = "data/bronze") -> list:
    """Lista arquivos CSV/XLSX disponíveis na camada local Bronze."""
    path = Path(local_dir)
    return list(path.rglob("*.csv")) + list(path.rglob("*.xlsx"))


def ingest_file_to_bronze(file_path: Path, s3_client) -> dict:
    """
    Ingere um arquivo para o S3 Bronze e retorna metadados.
    Não faz nenhuma transformação nos dados — apenas copia.
    """
    file_name = file_path.name
    fonte = file_path.parent.name
    timestamp = datetime.now(timezone.utc).isoformat()
    s3_key = f"{BRONZE_PREFIX}{fonte}/{file_name}"

    s3_client.upload_file(str(file_path), S3_BUCKET, s3_key)

    metadata = {
        "fonte": fonte,
        "arquivo": file_name,
        "s3_path": f"s3://{S3_BUCKET}/{s3_key}",
        "ingestao_timestamp": timestamp,
        "tamanho_bytes": file_path.stat().st_size,
    }

    # Salva metadados junto ao arquivo no S3
    meta_key = s3_key.replace(file_name, f"_meta_{file_name}.json")
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=meta_key,
        Body=json.dumps(metadata, ensure_ascii=False, indent=2),
        ContentType="application/json",
    )

    return metadata


def run():
    print("=" * 60)
    print("BRONZE LAYER – Ingestão de Arquivos Raw")
    print("=" * 60)

    s3 = boto3.client("s3")
    files = list_bronze_files()

    if not files:
        print("⚠️  Nenhum arquivo encontrado em data/bronze/")
        print("   Execute primeiro: python scripts/download_inep.py")
        return

    resultados = []
    for f in files:
        print(f"\n📄 Ingerindo: {f.name}")
        try:
            meta = ingest_file_to_bronze(f, s3)
            resultados.append(meta)
            print(f"   ✓ {meta['s3_path']}")
        except Exception as e:
            print(f"   ✗ Erro: {e}")

    print(f"\n✅ Bronze concluído: {len(resultados)} arquivo(s) ingerido(s)")
    return resultados


if __name__ == "__main__":
    run()
