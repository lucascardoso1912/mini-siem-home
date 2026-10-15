"""Generate the detailed synthetic incident-triage PDF report."""

import argparse
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "reports" / "incident-triage-001.pdf"
INK = colors.HexColor("#17221C")
GREEN = colors.HexColor("#287744")
MUTED = colors.HexColor("#66746B")
LINE = colors.HexColor("#DCE4DC")
PALE = colors.HexColor("#F2F5F0")


def register_fonts() -> None:
    candidates = (
        Path("/usr/share/fonts/dejavu"),
        Path("/usr/share/fonts/truetype/dejavu"),
    )
    for directory in candidates:
        regular = directory / "DejaVuSans.ttf"
        bold = directory / "DejaVuSans-Bold.ttf"
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("LabSans", str(regular)))
            pdfmetrics.registerFont(TTFont("LabSans-Bold", str(bold)))
            pdfmetrics.registerFontFamily(
                "LabSans",
                normal="LabSans",
                bold="LabSans-Bold",
                italic="LabSans",
                boldItalic="LabSans-Bold",
            )
            return
    raise RuntimeError(
        "DejaVu Sans not found. Install the DejaVu fonts before exporting the PDF."
    )


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "Eyebrow", parent=base["Normal"], fontName="LabSans-Bold",
            fontSize=8, leading=11, textColor=GREEN, spaceAfter=8,
        ),
        "title": ParagraphStyle(
            "ReportTitle", parent=base["Title"], fontName="LabSans-Bold",
            fontSize=23, leading=28, textColor=INK, alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"], fontName="LabSans",
            fontSize=10, leading=15, textColor=MUTED, spaceAfter=18,
        ),
        "h1": ParagraphStyle(
            "SectionHeading", parent=base["Heading2"], fontName="LabSans-Bold",
            fontSize=14, leading=18, textColor=INK, spaceBefore=12, spaceAfter=7,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "SubHeading", parent=base["Heading3"], fontName="LabSans-Bold",
            fontSize=10, leading=14, textColor=GREEN, spaceBefore=8, spaceAfter=4,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName="LabSans",
            fontSize=9, leading=14, textColor=INK, spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName="LabSans",
            fontSize=7.3, leading=10, textColor=INK,
        ),
        "table_head": ParagraphStyle(
            "TableHead", parent=base["Normal"], fontName="LabSans-Bold",
            fontSize=7.3, leading=9, textColor=colors.white,
        ),
        "callout": ParagraphStyle(
            "Callout", parent=base["BodyText"], fontName="LabSans-Bold",
            fontSize=8.5, leading=13, textColor=INK,
        ),
        "center": ParagraphStyle(
            "Center", parent=base["Normal"], fontName="LabSans",
            fontSize=7.3, leading=10, textColor=MUTED, alignment=TA_CENTER,
        ),
    }


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def make_table(
    rows: list[list[str]],
    styles: dict[str, ParagraphStyle],
    widths: list[float],
) -> Table:
    data = [
        [paragraph(cell, styles["table_head"]) for cell in rows[0]],
        *[
            [paragraph(cell, styles["small"]) for cell in row]
            for row in rows[1:]
        ],
    ]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def add_section(story: list, title: str, styles: dict[str, ParagraphStyle]) -> None:
    story.append(paragraph(title, styles["h1"]))


def draw_page(canvas, document) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(document.leftMargin, height - 14 * mm, width - document.rightMargin, height - 14 * mm)
    canvas.setFont("LabSans-Bold", 7)
    canvas.setFillColor(GREEN)
    canvas.drawString(document.leftMargin, height - 11 * mm, "LOCAL SOC LAB / RELATÓRIO DE TRIAGEM")
    canvas.setFont("LabSans", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(document.leftMargin, 10 * mm, "SIMULAÇÃO SINTÉTICA · SEM TELEMETRIA REAL")
    canvas.drawRightString(width - document.rightMargin, 10 * mm, f"Página {document.page}")
    canvas.restoreState()


def build_report(output: Path) -> None:
    register_fonts()
    styles = make_styles()
    output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=21 * mm,
        bottomMargin=18 * mm,
        title="Análise simulada 001 - falhas de login seguidas de sucesso",
        author="Local SOC Home Lab",
        subject="Relatório didático de triagem de alertas sintéticos",
    )
    story = []

    story.extend(
        [
            paragraph("SECURITY OPERATIONS / HOME LAB", styles["eyebrow"]),
            paragraph("Análise simulada de incidente", styles["title"]),
            paragraph(
                "Falhas de autenticação seguidas de login bem-sucedido",
                styles["subtitle"],
            ),
            paragraph(
                "SIMULAÇÃO — Nenhum host, usuário, pacote de rede ou conta real foi "
                "monitorado. O IP 203.0.113.66 pertence a uma faixa reservada para "
                "documentação e não identifica uma origem real.",
                styles["callout"],
            ),
            Spacer(1, 8),
        ]
    )

    add_section(story, "1. Resumo executivo", styles)
    story.append(
        paragraph(
            "O cenário <b>compromised</b>, seed <b>2026</b>, gerou 16 eventos "
            "sintéticos. Cinco falhas de login para <b>admin</b> ocorreram do mesmo "
            "IP entre 12:30 e 12:34 UTC; um sucesso para a mesma conta e origem veio "
            "às 12:35 UTC. O detector produziu um alerta <b>medium</b> de falhas "
            "repetidas e um alerta <b>high</b> pela correlação com o sucesso. O alerta "
            "high foi registrado como <b>investigating</b>; o medium permanece "
            "<b>open</b>.",
            styles["body"],
        )
    )
    story.append(
        paragraph(
            "Conclusão do exercício: os eventos satisfazem as regras implementadas. "
            "Isso não prova comprometimento real; é necessário validar fontes "
            "originais e contexto antes de classificar um incidente.",
            styles["body"],
        )
    )

    add_section(story, "2. Escopo e reprodução", styles)
    story.append(
        make_table(
            [
                ["Item", "Valor", "O que representa"],
                ["Cenário / seed", "compromised / 2026", "Entrada reproduzível do simulador."],
                ["Eventos", "16", "10 eventos de contexto e 6 eventos da sequência de teste."],
                ["Host", "auth-server-01", "Nome fictício incluído pelo gerador."],
                ["Run ID", "ac958c2bb9d5494b921fd16a81719abc", "Execução registrada no SQLite local."],
                ["Resposta", "Nenhuma", "Nenhum bloqueio ou ação automática foi executado."],
            ],
            styles,
            [34 * mm, 59 * mm, 81 * mm],
        )
    )
    story.append(Spacer(1, 7))
    story.append(paragraph("Reprodução sem alterar o banco principal:", styles["body"]))
    story.append(
        paragraph(
            "./.venv/bin/python -m soc_lab.simulator --scenario compromised --seed 2026 "
            "--output /tmp/soc-lab-compromised-2026.jsonl<br/>"
            "./.venv/bin/python -m soc_lab.cli --input /tmp/soc-lab-compromised-2026.jsonl "
            "--db /tmp/soc-lab-analysis.sqlite",
            styles["small"],
        )
    )

    add_section(story, "3. Linha do tempo observada", styles)
    story.append(
        make_table(
            [
                ["Horário UTC", "Evento sintético", "Interpretação"],
                ["12:30", "Falha para admin de 203.0.113.66", "Primeira falha."],
                ["12:31–12:33", "Mais três falhas para a mesma conta e origem", "Contagem sobe para quatro."],
                ["12:34", "Quinta falha para a mesma conta e origem", "A regra de falhas repetidas atinge o limiar 5/10 min."],
                ["12:35", "Sucesso para admin do mesmo IP", "A regra de correlação encontra sucesso em até 5 min."],
            ],
            styles,
            [27 * mm, 74 * mm, 73 * mm],
        )
    )

    add_section(story, "4. Significado dos campos", styles)
    story.append(
        make_table(
            [
                ["Campo", "Exemplo", "Significado / limite"],
                ["timestamp", "12:30–12:35 UTC", "Tempo fictício do evento; UTC facilita ordenar fontes."],
                ["event_type", "authentication", "Classifica o registro; não é captura de pacote."],
                ["source_ip", "203.0.113.66", "IP sintético. Não identifica uma pessoa nem uma rede real."],
                ["username", "admin", "Conta-alvo fictícia; não revela quem tentou autenticar."],
                ["outcome", "failure / success", "Resultado produzido pelo simulador, não confirmado por um IdP real."],
                ["hostname", "auth-server-01", "Nome de host fictício atribuído aos eventos."],
                ["event_id", "evt-0011…evt-0016", "Identificador sequencial para localizar registros no conjunto."],
                ["scenario", "compromised", "Rótulo do teste; não é veredito de incidente."],
            ],
            styles,
            [29 * mm, 47 * mm, 98 * mm],
        )
    )

    add_section(story, "5. Regras acionadas", styles)
    story.append(
        paragraph(
            "<b>multiple_failed_logins — medium.</b> Agrupa falhas por IP e verifica "
            "se há pelo menos cinco em uma janela móvel de dez minutos. Esta regra "
            "não precisa saber o usuário; por isso não é a regra que afirma que "
            "admin autenticou com sucesso.",
            styles["body"],
        )
    )
    story.append(
        paragraph(
            "<b>successful_login_after_failures — high.</b> Correlaciona pelo par "
            "IP + usuário. Encontrou cinco falhas para admin entre 12:30 e 12:34 e "
            "um sucesso às 12:35. A diferença de um minuto está dentro da janela "
            "configurada de cinco minutos, então a severidade foi elevada.",
            styles["body"],
        )
    )
    story.append(
        paragraph(
            "São dois alertas sobre os mesmos eventos, não duas ocorrências "
            "independentes. Um SIEM mais completo poderia agrupar ambos em um único "
            "caso para reduzir duplicidade.",
            styles["body"],
        )
    )

    add_section(story, "6. Raciocínio de triagem", styles)
    story.append(
        make_table(
            [
                ["Categoria", "Análise"],
                ["Observação", "Cinco falhas e um sucesso subsequente compartilham o mesmo IP e usuário no conjunto gerado."],
                ["Hipótese", "Se fossem logs reais, a sequência justificaria investigar uso de credenciais após tentativas repetidas."],
                ["Não demonstrado", "Não há evidência de senha descoberta, acesso real, identidade do operador, MFA ou atividade pós-login."],
                ["Alternativas benignas", "Erro de digitação antes do sucesso, teste autorizado, suporte ou endereço intermediário compartilhado."],
                ["Confiança", "Alta de que a regra corresponde aos eventos sintéticos; nenhuma conclusão sobre um ambiente real."],
            ],
            styles,
            [37 * mm, 137 * mm],
        )
    )

    add_section(story, "7. Decisão registrada e próximos passos", styles)
    story.append(
        paragraph(
            "O alerta high, ID <b>22d19b8ead764333bb959ce0bde6812f</b>, está "
            "<b>investigating</b>. A nota persistida marca explicitamente a simulação "
            "e recomenda verificar logs originais antes de concluir comprometimento. "
            "O alerta medium, ID <b>c53808f573ce4dec8578f0303dc0605f</b>, permanece "
            "<b>open</b>.",
            styles["body"],
        )
    )
    for step in (
        "Confirmar IP, host, usuário e método nos logs originais do sistema ou provedor de identidade.",
        "Verificar se o sucesso e o dispositivo/sessão eram esperados e revisar atividade posterior.",
        "Consultar MFA, origem e histórico da conta para comparação com o comportamento normal.",
        "Se evidências reais confirmarem risco, seguir o procedimento autorizado da organização para proteger a conta e revogar sessões.",
    ):
        story.append(paragraph(f"• {step}", styles["body"]))

    add_section(story, "8. Limitações e conclusão", styles)
    story.append(
        paragraph(
            "O laboratório analisou somente JSONL sintético. Não leu logs do "
            "Windows/Linux, não observou tráfego, não analisou TCP/UDP e não executou "
            "resposta automática. O estado <b>investigating</b> é parte do exercício. "
            "Nunca bloquear o IP de documentação com base neste resultado; em caso "
            "real, validar evidências originais e seguir o processo autorizado.",
            styles["body"],
        )
    )
    story.append(Spacer(1, 12))
    story.append(
        paragraph(
            "Relatório educativo do SOC Home Lab · cenário sintético · "
            "não representa um incidente real",
            styles["center"],
        )
    )

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    print(f"PDF gerado: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the simulated incident report to PDF")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build_report(args.output)


if __name__ == "__main__":
    main()