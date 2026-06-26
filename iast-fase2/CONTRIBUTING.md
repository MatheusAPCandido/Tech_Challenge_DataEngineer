# Guia de Contribuição – IAST Fase 2

## Fluxo de Trabalho com Git

### Branches

| Branch | Uso |
|--------|-----|
| `main` | Código estável, pronto para entrega |
| `develop` | Integração das features em desenvolvimento |
| `feature/nome-da-feature` | Nova funcionalidade |
| `fix/nome-do-bug` | Correção de bugs |

### Passo a Passo para Contribuir

```bash
# 1. Atualize o develop local
git checkout develop
git pull origin develop

# 2. Crie uma branch para sua tarefa
git checkout -b feature/pipeline-silver

# 3. Faça seu trabalho e commits
git add .
git commit -m "feat: adiciona limpeza de valores nulos na Silver Layer"

# 4. Envie para o GitHub
git push origin feature/pipeline-silver

# 5. Abra um Pull Request para develop no GitHub
```

### Padrão de Commits (Conventional Commits)

Use prefixos para deixar o histórico claro:

| Prefixo | Quando usar |
|---------|-------------|
| `feat:` | Nova funcionalidade |
| `fix:` | Correção de bug |
| `docs:` | Documentação |
| `refactor:` | Refatoração sem mudança de comportamento |
| `test:` | Adição ou correção de testes |
| `infra:` | Infraestrutura (Terraform, CI/CD) |
| `chore:` | Tarefas de manutenção |

**Exemplos:**
```
feat: cria script de download das bases do INEP
fix: corrige encoding latin-1 no CSV de alfabetização
docs: atualiza README com diagrama de arquitetura
infra: adiciona lifecycle policy no bucket S3
test: adiciona validação de código IBGE na Silver
```

### Pull Requests

- Descreva o que foi feito e por quê
- Mencione o issue relacionado com `Closes #N`
- Aguarde revisão de pelo menos 1 integrante antes de mergear

### Divisão sugerida de tarefas

| Integrante | Responsabilidade |
|------------|-----------------|
| 1 | Bronze Layer + download INEP |
| 2 | Silver Layer + qualidade de dados |
| 3 | Gold Layer + Terraform + README |
