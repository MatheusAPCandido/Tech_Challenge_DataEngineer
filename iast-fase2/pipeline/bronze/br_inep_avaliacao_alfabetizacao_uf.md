# Dicionário de dados — br_inep_avaliacao_alfabetizacao_uf

**Fonte:** Base dos Dados — Avaliação da Alfabetização (INEP)
**Camada:** Bronze
**Data de ingestão:** 2026-07-02
**Granularidade:** 1 linha por (ano, UF, série, rede)

## Colunas

| Coluna | Tipo | Descrição |
|---|---|---|
| ano | int | Ano de referência da avaliação (2023, 2024) |
| sigla_uf | string | Sigla da Unidade Federativa |
| serie | int | Série/ano escolar avaliado (observado: sempre `2`, referente ao 2º ano do Ensino Fundamental) |
| rede | int | Rede de ensino avaliada para construção do resultado (descrição oficial da fonte) |
| taxa_alfabetizacao | float | % de alunos alfabetizados (acima do ponto de corte 743 na escala Saeb) |
| media_portugues | float | Nota média em português na escala Saeb |
| proporcao_aluno_nivel_0 a _8 | float | Distribuição percentual dos alunos por nível de proficiência em português. **Disponível somente a partir de 2024** — nulo em 2023 por mudança de metodologia de publicação do INEP, não por erro de coleta. |

## ⚠️ Suposição documentada: dicionário da coluna `rede`

A fonte (Base dos Dados) descreve a coluna `rede` apenas como *"Rede de ensino avaliada para construção do resultado"*, **sem publicar o dicionário oficial de códigos** no momento da extração (02/07/2026).

Valores observados no dataset: `0, 2, 3, 5` (não aparecem `1` nem `4`).

Com base no padrão usual do INEP para dependência administrativa (Censo Escolar / Saeb), assumimos:

| Código | Suposição |
|---|---|
| 0 | Total (todas as redes, incluindo privada) |
| 2 | Estadual |
| 3 | Municipal |
| 5 | Pública (agregado: Federal + Estadual + Municipal) |

*(Códigos 1=Federal e 4=Privada não aparecem nesta tabela, coerente com o foco em redes públicas.)*

**Evidência de suporte:** nas linhas da Bahia (2024), os valores de `rede=3` (Municipal), `rede=5` (Pública) e `rede=0` (Total) são quase idênticos entre si, enquanto `rede=2` (Estadual) difere — consistente com a rede Municipal dominar o agregado público na BA.

**Ação de acompanhamento:** revisar esta suposição caso a fonte publique o dicionário oficial de valores. Até lá, essa tabela De-Para será aplicada na camada Silver como uma transformação explícita e documentada (não fixa nem definitiva).

## Regra de qualidade de dados aplicada

- `proporcao_aluno_nivel_*` nulo em 2023 → **manter nulo** (não preencher com 0), pois representa ausência de metodologia, não ausência real de alunos naquele nível.
