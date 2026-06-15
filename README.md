# Medição de Software + ACARI

Plataforma de análise de corpus acadêmico que produz **duas saídas a partir do
mesmo conjunto de dados**:

1. **Grafo 3D interativo** (extensível, data-driven) — `visualizacao/`.
2. **ACARI** — *Avaliador de Corpus Acadêmico por Relevância e Indexação*,
   agora **portado para dentro do pacote** (`src/medicao/slices/acari/`), que
   mede o alinhamento semântico do corpus com a disciplina.

Os dois consomem o **mesmo contrato de dados** (um *bundle*): o mesmo
`artigos.csv` alimenta o grafo e o ACARI.

## Contrato de dados (bundle)

Um *bundle* é uma pasta em `datasets/<nome>/` com datasets padronizados:

| Dataset | Arquivo | Grafo 3D | ACARI | Obrigatório |
|---|---|---|---|---|
| **artigos** | `artigos.csv` | nós de artigo | corpus (o mesmo CSV) | **Sim** |
| **ementa** | `ementa.csv` | nós de ementa | vira `ementa.txt` (disciplina) | **Sim** |
| **aulas** | `aulas.csv` | nós de aula | — | Opcional |

Saídas geradas: `relacoes.csv`, `graph.json` (visualização), `ementa.txt` e a
pasta `acari/` (saídas do pipeline ACARI: `data/`, `figs/`, `tables/`, `logs/`).

Templates prontos em `datasets/_templates/` (`artigos`, `ementa`, `aulas`,
`manifest`). A única coluna obrigatória de `artigos.csv` é **`title`** (o
esquema é a fusão das colunas do ACARI com os campos ricos de medição).

**Campo opcional importante**: `cohort` — identifica a turma/grupo de cada
artigo (ex: `"Turma A 2025/1"`). Quando preenchido, habilita análises
comparativas entre turmas (hipóteses H2/H3, figuras por turma). Quando vazio,
essas análises são puladas graciosamente.

### Dados brutos (PDFs e fonte da ementa)

A pasta `data/` é organizada **por bundle**:

```
data/
├── medicao/               # bundle "medicao"
│   ├── raw/artigos/       # PDFs de artigos
│   ├── raw/aulas/         # PDFs de aulas (opcional)
│   └── ementa/            # ementa.pdf, ementa.csv, cronograma
├── <outro_bundle>/        # outro bundle
│   ├── raw/artigos/
│   ├── raw/aulas/
│   └── ementa/
```

Cada bundle tem seus próprios PDFs e sua própria ementa. O pipeline lê de
`data/<bundle>/` e grava as saídas em `datasets/<bundle>/`.

## Arquitetura (Vertical Slice)

```
src/medicao/
├── shared/        # config (bundles), contract (schemas + Bundle), pdf, text, storage
├── slices/
│   ├── artigos/   # PDFs -> artigos.csv (schema fundido ACARI+medição)
│   ├── ementa/    # ementa.csv -> ementa.txt (+ migração do cronograma)
│   ├── aulas/     # PDFs de slides -> aulas.csv (opcional)
│   ├── relacoes/  # artigos x ementa -> relacoes.csv
│   ├── grafo/     # bundle -> graph.json genérico (auto-descritivo)
│   ├── web/       # registro datasets/index.json
│   └── acari/     # pipeline ACARI portado
│       ├── pipeline.py   # orquestrador (ingest -> ... -> export_latex)
│       └── steps/        # ingest, enrich, venue, textsim, baseline, network,
│                         # rubric, index, stats, viz, export_latex, config
├── pipeline.py    # orquestrador do bundle
└── __main__.py    # CLI

datasets/          # bundles + templates + index.json
data/raw/          # PDFs brutos de artigos e aulas
data/ementa/       # fonte da disciplina: ementa.pdf (oficial) + ementa.csv + cronograma
visualizacao/      # grafo 3D data-driven (index.html)
```

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt          # extrator/grafo (PyMuPDF)
pip install -r requirements-acari.txt    # ACARI (embeddings, redes, figuras, ...)
```

## Uso

### Gerar o bundle (a partir dos PDFs)

```bash
PYTHONPATH=src python3 -m medicao            # pipeline completo
PYTHONPATH=src python3 -m medicao artigos    # uma etapa
PYTHONPATH=src python3 -m medicao --bundle medicao
```

### Visualizar o grafo 3D

Sirva a partir da **raiz do repositório**:

```bash
python3 -m http.server 8000
# abra http://localhost:8000/visualizacao/
```

O seletor lista os bundles de `datasets/index.json`; a renderização é genérica
(cores/filtros vêm do `manifest`), então qualquer bundle novo aparece sozinho.

### Gerar evidências do Grupo 2

```bash
PYTHONPATH=src python3 -m medicao grupo2
```

Saídas no bundle:

- `grupo2_respostas.csv` — tabela por artigo com temas, veículo, relação com a
  ementa, proxies de qualidade e pendências.
- `grupo2_auditoria.csv` — cobertura dos dados necessários para responder RQ01
  a RQ05 e aos itens do enunciado.
- `grupo2_resumo.json` — resumo rápido da cobertura.

### Rodar o ACARI (agora interno ao pacote)

```bash
PYTHONPATH=src python3 -m medicao acari                 # prepara (gera ementa.txt) e valida
PYTHONPATH=src python3 -m medicao acari --run-acari     # executa o pipeline completo
PYTHONPATH=src python3 -m medicao acari --run-acari --acari-only ingest   # só uma etapa
PYTHONPATH=src python3 -m medicao acari --run-acari --acari-from textsim  # a partir de uma etapa
```

As saídas vão para `datasets/<bundle>/acari/`. As etapas de embeddings/rede/
enriquecimento exigem `requirements-acari.txt` e acesso à internet (OpenAlex e
download do modelo na 1ª execução).

## Criar um novo dataset (extensível)

1. Crie `datasets/<seu_bundle>/`.
2. Preencha `artigos.csv` e `ementa.csv` a partir de `datasets/_templates/`.
3. Gere grafo e índice e (opcional) rode o ACARI:

```bash
PYTHONPATH=src python3 -m medicao grafo --bundle <seu_bundle>
PYTHONPATH=src python3 -m medicao web
PYTHONPATH=src python3 -m medicao acari --run-acari --bundle <seu_bundle>
```

## Configuração

- `MEDICAO_BUNDLES_DIR` — raiz dos bundles (default: `datasets/`)
- `MEDICAO_RAW_DIR` — PDFs brutos (default: `data/raw/`)
- `MEDICAO_WEB_DIR` — visualização (default: `visualizacao/`)
- `MEDICAO_BUNDLE` — bundle default (default: `medicao`)
