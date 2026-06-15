# Templates de Datasets

Templates para criar um novo bundle em `datasets/<nome>/`.

## artigos.template.csv

Campos obrigatórios: `id`, `title`

Campos opcionais relevantes:

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| `cohort` | Turma/grupo do artigo. Habilita análises comparativas entre turmas (H2, H3) e a figura de distribuição temática por turma. Se vazio, essas análises são puladas graciosamente. | `"Turma A 2025/1"` |
| `venue_type` | Tipo de veículo (journal, conference, preprint, book, report, magazine, thesis). Pode ser preenchido manualmente ou via enriquecimento ACARI. | `"journal"` |
| `in_statistical_test` | Se o artigo entra nos testes estatísticos (`True`/`False`). Artigos com venue_type em {book, report, magazine, thesis, chapter} são excluídos automaticamente. | `"True"` |
| `article_authors` | Autores no formato "Sobrenome, I." ou "Sobrenome, I. et al." | `"Silva, J. et al."` |

Todos os demais campos são preenchidos automaticamente pelo extrator de PDFs ou pelo pipeline ACARI (enrich, venue, textsim, etc.).

## ementa.template.csv

Campos obrigatórios: `id`, `topico`

## aulas.template.csv

Campos obrigatórios: `id`, `titulo`

## manifest.template.json

Metadados do bundle. Gerado automaticamente pelo pipeline, mas pode ser editado manualmente.
