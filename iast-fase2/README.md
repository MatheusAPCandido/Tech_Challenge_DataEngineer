# 📚 IAST Tech Challenge – Fase 2: Pipeline de Alfabetização

## Contexto do Problema

O Brasil enfrenta um desafio histórico de alfabetização. O **Compromisso Nacional Criança Alfabetizada** estabelece metas municipais de alfabetização até os 8 anos de idade. Acompanhar a evolução desse indicador por município é essencial para direcionar políticas públicas eficazes.

Este projeto constrói uma **pipeline de dados escalável na AWS** que integra os dados do INEP para produzir indicadores analíticos prontos para dashboards, análises estatísticas e modelos de machine learning.

---

## 🏗️ Arquitetura da Solução

```
INEP (Fonte)
    │
    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   BRONZE    │────▶│   SILVER    │────▶│    GOLD     │
│  Raw Data   │     │  Tratados   │     │  Analítico  │
│  (S3 + CSV) │     │ (S3+Parquet)│     │ (S3+Parquet)│
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │AWS Athena   │
                                        │ Dashboards  │
                                        │     ML      │
                                        └─────────────┘
```

**Ferramentas utilizadas:**

| Camada | Serviço AWS | Justificativa |
|--------|-------------|---------------|
| Ingestão | AWS Glue (Crawler + Job) | Serverless, sem infra para gerenciar |
| Armazenamento | AWS S3 | Custo baixo, escalável, integrado ao Glue |
| Transformação | AWS Glue + PySpark | Processamento distribuído nativo |
| Consulta analítica | AWS Athena | SQL direto no S3, pago por query |
| Orquestração | AWS Glue Workflows | Nativo, sem custo extra de ferramenta |
| IaC | Terraform | Reprodutível e versionável |

---

## 📊 Diagrama da Pipeline

```
[Download INEP] → [S3 Bronze] → [Glue Job: Bronze→Silver] → [S3 Silver]
                                                                   │
                                          [Glue Job: Silver→Gold] ┘
                                                   │
                                            [S3 Gold]
                                                   │
                                          [AWS Athena / BI]
```

---

## 🗂️ Estrutura do Repositório

```
iast-fase2/
├── pipeline/
│   ├── bronze/         # Scripts de ingestão raw
│   ├── silver/         # Scripts de limpeza e transformação
│   ├── gold/           # Scripts de agregação analítica
│   └── utils/          # Funções auxiliares compartilhadas
├── scripts/
│   └── download_inep.py  # Download automático das bases do INEP
├── tests/              # Testes de qualidade de dados
├── infrastructure/
│   └── terraform/      # Infraestrutura AWS como código
├── notebooks/          # Análises exploratórias
├── docs/               # Documentação adicional
└── data/               # Amostras locais (não sobe ao Git)
```

---

## 🚀 Como Executar

### Pré-requisitos
- Python 3.10+
- AWS CLI configurado (`aws configure`)
- Terraform >= 1.5

### 1. Clonar o repositório
```bash
git clone https://github.com/SEU_ORG/iast-fase2.git
cd iast-fase2
pip install -r requirements.txt
```

### 2. Provisionar infraestrutura AWS
```bash
cd infrastructure/terraform
terraform init
terraform plan
terraform apply
```

### 3. Fazer download dos dados do INEP
```bash
python scripts/download_inep.py
```

### 4. Executar a pipeline
```bash
# Bronze → Silver
python pipeline/silver/transform_silver.py

# Silver → Gold
python pipeline/gold/build_gold.py
```

### 5. Validar qualidade dos dados
```bash
python tests/test_data_quality.py
```

---

## 💰 FinOps – Otimização de Custos

| Decisão | Impacto |
|---------|---------|
| Armazenamento em **Parquet** com compressão Snappy | Reduz tamanho em ~75% vs CSV |
| **Particionamento** por `ano` e `uf` no S3 | Athena lê menos dados por query |
| AWS Glue **serverless** | Paga só pelo tempo de execução |
| Athena **pago por query** | Sem custo de servidor ocioso |
| S3 **Lifecycle Policy** | Move dados antigos para S3 Glacier |

**Estimativa de custo mensal (dados do INEP ~500MB):**
- S3: ~$0.012/GB = < $1/mês
- Glue Job (1h/mês): ~$0.44
- Athena (10 queries/mês): ~$0.05
- **Total estimado: < $2/mês**

---

## 🤖 Aplicação em IA

A camada **Gold** está preparada para:

- **Modelos preditivos** de alfabetização por município (features: IDH, infraestrutura escolar, investimento FUNDEB)
- **Clustering** de municípios por vulnerabilidade educacional
- **Séries temporais** para projeção de metas futuras
- **Análise de desigualdade** regional com correlação socioeconômica

---

## 👥 Time

| Nome | GitHub |
|------|--------|
| Integrante 1 | @usuario1 |
| Integrante 2 | @usuario2 |
| Integrante 3 | @usuario3 |

---

## 📎 Referências

- [INEP – Indicadores Educacionais](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais)
- [Compromisso Nacional Criança Alfabetizada](https://www.gov.br/mec/pt-br/crianca-alfabetizada)
- [AWS Glue Documentation](https://docs.aws.amazon.com/glue/)
