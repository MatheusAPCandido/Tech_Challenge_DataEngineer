"""
Script de download automático das bases do INEP:
- Indicador de Alfabetização por município
- Metas do Compromisso Nacional Criança Alfabetizada
"""

import os
import requests
import zipfile
import boto3
from pathlib import Path

# Configurações
S3_BUCKET = os.environ.get("S3_BUCKET", "iast-fase2-datalake")
BRONZE_PREFIX = "bronze/inep/"
LOCAL_DATA_DIR = Path("data/bronze")

# URLs das bases do INEP (atualizar conforme versão mais recente)
SOURCES = {
    "indicador_alfabetizacao": (
        "https://download.inep.gov.br/informacoes_estatisticas/"
        "indicadores_educacionais/taxa_alfabetizacao/"
        "taxa_alfabetizacao_municipios_2023.zip"
    ),
    "metas_compromisso": (
        "https://download.inep.gov.br/informacoes_estatisticas/"
        "indicadores_educacionais/metas_compromisso_alfabetizacao/"
        "metas_municipios_2023.zip"
    ),
}


def download_file(url: str, dest_path: Path) -> Path:
    """Baixa um arquivo da URL e salva localmente."""
    print(f"Baixando: {url}")
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"  ✓ Salvo em: {dest_path}")
    return dest_path


def extract_zip(zip_path: Path, extract_to: Path) -> list:
    """Extrai um zip e retorna lista de arquivos extraídos."""
    extract_to.mkdir(parents=True, exist_ok=True)
    extracted = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)
        extracted = [extract_to / name for name in zf.namelist()]

    print(f"  ✓ Extraído: {len(extracted)} arquivo(s)")
    return extracted


def upload_to_s3(local_path: Path, s3_key: str, bucket: str = S3_BUCKET):
    """Faz upload de um arquivo local para o S3 Bronze."""
    s3 = boto3.client("s3")
    print(f"  Enviando para s3://{bucket}/{s3_key} ...")
    s3.upload_file(str(local_path), bucket, s3_key)
    print(f"  ✓ Upload concluído")


def run():
    print("=" * 60)
    print("INGESTÃO BRONZE – Download das bases do INEP")
    print("=" * 60)

    for name, url in SOURCES.items():
        print(f"\n📥 Fonte: {name}")

        # Download
        zip_path = LOCAL_DATA_DIR / f"{name}.zip"
        try:
            download_file(url, zip_path)
        except Exception as e:
            print(f"  ⚠️  Falha no download: {e}")
            print("  → Verifique a URL ou baixe manualmente do site do INEP")
            continue

        # Extração
        extract_dir = LOCAL_DATA_DIR / name
        files = extract_zip(zip_path, extract_dir)

        # Upload para S3
        for file_path in files:
            if file_path.is_file():
                s3_key = f"{BRONZE_PREFIX}{name}/{file_path.name}"
                try:
                    upload_to_s3(file_path, s3_key)
                except Exception as e:
                    print(f"  ⚠️  Falha no upload S3: {e}")
                    print("  → Verifique suas credenciais AWS (aws configure)")

    print("\n✅ Ingestão Bronze concluída!")
    print(f"   Dados em: s3://{S3_BUCKET}/{BRONZE_PREFIX}")


if __name__ == "__main__":
    run()
