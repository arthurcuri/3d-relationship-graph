from __future__ import annotations

from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parent
OUT_DIR = REPO_ROOT / "outputs" / "pipeline_detalhado"
OUT_FILE = OUT_DIR / "pipeline_grafo_detalhada.png"


W, H = 1450, 2280
BLUE = "#073B82"
BLUE2 = "#0B55B7"
LIGHT = "#F8FBFF"
BORDER = "#8AB8F4"
TEXT = "#101828"
MUTED = "#475467"
LINE = "#D7E7FF"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:/Windows/Fonts/arialbd.ttf" if bold else r"C:/Windows/Fonts/arial.ttf",
        r"C:/Windows/Fonts/calibrib.ttf" if bold else r"C:/Windows/Fonts/calibri.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


F_TITLE = font(54, True)
F_SUB = font(25)
F_H = font(26, True)
F_BODY = font(17)
F_BODY_B = font(18, True)
F_SMALL = font(15)
F_NUM = font(25, True)


def rounded(draw: ImageDraw.ImageDraw, box, radius=18, fill="white", outline=BORDER, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def arrow(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, color=BLUE2, width=8):
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    if x1 == x2:
        draw.polygon([(x2, y2), (x2 - 14, y2 - 20), (x2 + 14, y2 - 20)], fill=color)
    else:
        draw.polygon([(x2, y2), (x2 - 22, y2 - 14), (x2 - 22, y2 + 14)], fill=color)


def draw_wrapped(draw, xy, text, width_chars, fill=TEXT, fnt=F_BODY, spacing=4):
    x, y = xy
    for line in textwrap.wrap(text, width=width_chars):
        draw.text((x, y), line, fill=fill, font=fnt)
        y += fnt.size + spacing
    return y


def icon_box(draw, x, y, label):
    rounded(draw, (x, y, x + 88, y + 72), radius=12, fill="#FFFFFF", outline="#BBD6FF", width=2)
    draw.text((x + 44, y + 18), label, fill=BLUE, font=F_BODY_B, anchor="mm")


def step(draw, n, title, body, y, icon):
    x, w, h = 45, 930, 118
    rounded(draw, (x, y, x + w, y + h), radius=18, fill=LIGHT, outline=BORDER, width=2)
    draw.ellipse((x + 18, y + 20, x + 68, y + 70), fill=BLUE)
    draw.text((x + 43, y + 45), str(n), fill="white", font=F_NUM, anchor="mm")
    icon_box(draw, x + 95, y + 23, icon)
    draw.text((x + 205, y + 18), title, fill=BLUE, font=F_H)
    draw_wrapped(draw, (x + 205, y + 52), body, 86, fill=TEXT, fnt=F_BODY, spacing=3)
    return y + h


def panel(draw, x, y, w, h, letter, title, items):
    rounded(draw, (x, y, x + w, y + h), radius=20, fill="white", outline=BLUE2, width=2)
    draw.rounded_rectangle((x, y, x + w, y + 72), radius=20, fill=BLUE, outline=BLUE)
    draw.ellipse((x + 20, y + 16, x + 66, y + 62), fill="white")
    draw.text((x + 43, y + 39), letter, fill=BLUE, font=F_NUM, anchor="mm")
    draw.text((x + 85, y + 24), title, fill="white", font=F_H)
    yy = y + 95
    for head, text in items:
        draw.text((x + 30, yy), head, fill=BLUE, font=F_BODY_B)
        draw_wrapped(draw, (x + 100, yy), text, 34, fill=TEXT, fnt=F_BODY, spacing=4)
        yy += 86
        draw.line((x + 24, yy - 18, x + w - 24, yy - 18), fill=LINE, width=2)


def main():
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    draw.text((W / 2, 35), "Pipeline detalhada do grafo 3D", fill="#08245C", font=F_TITLE, anchor="ma")
    draw.text(
        (W / 2, 104),
        "Fluxo de preparação do dataset e geração da visualização interativa",
        fill=MUTED,
        font=F_SUB,
        anchor="ma",
    )

    # Fluxo geral
    rounded(draw, (42, 150, 1408, 330), radius=18, fill="white", outline=BLUE2, width=2)
    draw.text((62, 172), "Fluxo geral:", fill=BLUE, font=F_BODY_B)
    flow = [
        ("PDFs", "PDFs dos artigos\n+ PDFs das aulas\n+ ementa"),
        ("EXT", "extração\ndos dados"),
        ("CSV", "artigos.csv /\naulas.csv /\nementa.csv"),
        ("REL", "relacoes.csv"),
        ("JSON", "graph.json"),
        ("WEB", "visualizacao/\nindex.html"),
    ]
    fx = 92
    for i, (ic, txt) in enumerate(flow):
        icon_box(draw, fx, 212, ic)
        draw.multiline_text((fx + 44, 292), txt, fill=TEXT, font=F_SMALL, anchor="ma", align="center", spacing=2)
        if i < len(flow) - 1:
            arrow(draw, fx + 105, 248, fx + 160, 248, width=7)
        fx += 200

    steps = [
        ("Entrada dos dados", "A pipeline começa lendo os arquivos brutos: data/raw/artigos, data/raw/aulas e data/ementa. Essas pastas contêm PDFs dos artigos, PDFs das aulas e a ementa/plano de ensino. São os arquivos originais usados para montar o dataset.", "IN"),
        ("Extração dos artigos", "Os PDFs dos artigos são lidos e organizados em datasets/medicao/artigos.csv. Cada linha representa um artigo. Campos: id, title, authors, year, doi, abstract, keywords, venue_type, arquivo, paginas, referencias, metodologia, areas, metricas, metodos_estatisticos, idioma e caminho_pdf.", "CSV"),
        ("Extração das aulas", "Os PDFs das aulas são lidos e organizados em datasets/medicao/aulas.csv. Cada aula vira um item estruturado e pode aparecer no grafo como nó de apoio, conectando artigos com conteúdos vistos na disciplina.", "AUL"),
        ("Preparação da ementa", "A ementa/plano de ensino é processada e organizada em datasets/medicao/ementa.csv. Também é gerado datasets/medicao/ementa.txt. No grafo, cada tópico da ementa pode virar um nó.", "EMT"),
        ("Cálculo das relações", "A pipeline compara artigos com tópicos da ementa usando título, abstract, palavras-chave, áreas, metodologia e métricas. A saída é datasets/medicao/relacoes.csv com artigo_id, ementa_id, score_relevancia e percentual_match.", "REL"),
        ("Criação dos nós do grafo", "A pipeline cria nós dos tipos artigo, ementa e aula. Cada artigo vira um nó com metadados; cada tópico da ementa vira um nó; cada aula vira um nó. Os nós carregam título, ano, PDF, área e descrição.", "NÓ"),
        ("Criação das arestas", "As arestas representam as ligações entre nós. A principal ligação é artigo -> tópico da ementa, baseada em relacoes.csv. A força da relação vem de score_relevancia e percentual_match.", "EDG"),
        ("Geração do graph.json", "O grafo é exportado para datasets/medicao/graph.json. Esse arquivo contém nós, arestas, tipo de cada nó, cores, labels, metadados, links para PDFs e informações para exibir na interface.", "JS"),
        ("Visualização 3D", "A interface fica em visualizacao/index.html. Ela lê graph.json e renderiza o grafo, permitindo visualizar artigos, aulas, tópicos da ementa, conexões, concentração por tema e sobreposição temática.", "3D"),
        ("Manifest e index dos datasets", "A pipeline atualiza datasets/medicao/manifest.json e datasets/index.json. Esses arquivos dizem para a visualização quais datasets existem e como carregar cada um.", "CFG"),
        ("Arquivos de apoio do Grupo 2", "Além do grafo, gera grupo2_respostas.csv, grupo2_auditoria.csv e grupo2_resumo.json. Eles ajudam a responder perguntas do enunciado sobre temas, alinhamento, sobreposição, dados faltantes e cobertura.", "G2"),
    ]

    y = 360
    for i, (title, body, ic) in enumerate(steps, 1):
        y_end = step(draw, i, title, body, y, ic)
        if i < len(steps):
            arrow(draw, 510, y_end + 2, 510, y_end + 30, width=6)
        y = y_end + 35

    panel(
        draw,
        1010,
        360,
        395,
        485,
        "A",
        "Estrutura do grafo",
        [
            ("Nós", "Tipos de nós: artigo, ementa e aula."),
            ("Aresta", "Ligação principal: artigo -> tópico da ementa."),
            ("Peso", "Força da relação: score_relevancia + percentual_match."),
            ("Info", "Nós exibem metadados e links para PDFs."),
        ],
    )

    panel(
        draw,
        1010,
        885,
        395,
        640,
        "B",
        "Arquivos gerados",
        [
            ("CSV", "artigos.csv"),
            ("CSV", "aulas.csv"),
            ("CSV", "ementa.csv e ementa.txt"),
            ("CSV", "relacoes.csv"),
            ("JSON", "graph.json"),
            ("WEB", "visualizacao/index.html"),
        ],
    )

    panel(
        draw,
        1010,
        1565,
        395,
        395,
        "C",
        "Diferença para ACARI",
        [
            ("Grafo", "Prepara dados e visualização 3D."),
            ("ACARI", "Faz enriquecimento, alinhamento, ARQI e testes estatísticos."),
            ("Uso", "O ACARI usa a base preparada pelo dataset/grafo."),
        ],
    )

    rounded(draw, (1010, 1995, 1405, 2225), radius=18, fill="#EEF6FF", outline=BORDER, width=2)
    draw.text((1035, 2020), "Resumo curto", fill=BLUE, font=F_H)
    draw_wrapped(
        draw,
        (1035, 2060),
        "A pipeline do grafo pega PDFs dos artigos, aulas e ementa, transforma tudo em CSVs estruturados, calcula relações entre artigos e tópicos da disciplina, gera o graph.json e alimenta a visualização 3D.",
        38,
        fill=TEXT,
        fnt=F_BODY,
        spacing=4,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUT_FILE, quality=95)
    print(OUT_FILE)


if __name__ == "__main__":
    main()
