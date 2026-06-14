# Medição de Software

Pipeline de extração e visualização do material da disciplina de **Medição e
Experimentação em Engenharia de Software**: artigos científicos (PDFs), slides
de aula (PDFs) e o cronograma da disciplina. Os dados são extraídos,
enriquecidos e relacionados, alimentando uma visualização 3D interativa.

## Arquitetura (Vertical Slice)

O código é organizado por **capacidade de domínio** (slice), não por camada
técnica. Cada slice é autocontido (extração, regras e pipeline) e depende
apenas de um kernel compartilhado.

```
src/medicao/
├── shared/                 # kernel transversal
│   ├── config.py           # caminhos (resolvidos a partir da raiz do repo)
│   ├── pdf.py              # leitura de PDF (PyMuPDF) + normalização NFC
│   ├── text.py            # utilitários de texto
│   └── storage.py         # leitura/escrita de CSV e JSON
├── slices/
│   ├── artigos/            # PDFs de artigos -> dataset_artigos.csv (rico)
│   ├── aulas/              # PDFs de slides  -> dataset_aulas.csv
│   ├── cronograma/         # CSV bruto       -> dataset_cronograma.csv
│   ├── relacoes/           # artigos x aulas -> dataset_relacoes_artigo_aula.csv
│   ├── grafo/              # datasets        -> visualizacao/graph_data.json
│   └── web/                # datasets        -> visualizacao/data.json
├── pipeline.py             # orquestrador (executa os slices em ordem)
└── __main__.py             # CLI: python -m medicao [slice]

data/
├── raw/                    # entradas (PDFs e cronograma)
│   ├── artigos/
│   └── aulas/
└── processed/              # datasets gerados (CSV)

visualizacao/               # front-end (index.html consome data.json)
```

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

Executar o pipeline completo:

```bash
PYTHONPATH=src python3 -m medicao
```

Executar um slice específico (`artigos`, `aulas`, `cronograma`, `relacoes`,
`web`, `grafo`):

```bash
PYTHONPATH=src python3 -m medicao artigos
```

> Os slices `relacoes`, `web` e `grafo` consomem os CSVs em `data/processed/`,
> então rode-os após os slices que os produzem (ou rode o pipeline completo).

## Visualização

Sirva a partir da **raiz do repositório** (para que os PDFs em `data/raw/`
fiquem acessíveis ao front-end):

```bash
python3 -m http.server 8000
# abra http://localhost:8000/visualizacao/
```

O `index.html` carrega `data.json` e renderiza o grafo de artigos, aulas e
cronograma. Os botões "Abrir PDF" usam caminhos relativos para `data/raw/`.

## Configuração

Os caminhos são resolvidos a partir da raiz do repositório. É possível
sobrescrever via variáveis de ambiente:

- `MEDICAO_DATA_DIR` — raiz dos dados (default: `data/`)
- `MEDICAO_WEB_DIR` — pasta da visualização (default: `visualizacao/`)
