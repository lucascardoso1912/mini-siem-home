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
        (Path("/usr/share/fonts/dejavu"), "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu"), "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        (Path("C:/Windows/Fonts"), "arial.ttf", "arialbd.ttf"),
    )
    for directory, regular_name, bold_name in candidates:
        regular = directory / regular_name
        bold = directory / bold_name
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
        "No supported font found (DejaVu Sans or Arial). Install DejaVu fonts before exporting the PDF."
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
    canvas.drawString(document.leftMargin, height - 11 * mm, "LOCAL SOC LAB / TRIAGE REPORT")
    canvas.setFont("LabSans", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(document.leftMargin, 10 * mm, "SYNTHETIC SIMULATION · NO REAL TELEMETRY")
    canvas.drawRightString(width - document.rightMargin, 10 * mm, f"Page {document.page}")
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
        title="Simulated analysis 001 - failed logins followed by a success",
        author="Local SOC Home Lab",
        subject="Teaching report on triage of synthetic alerts",
    )
    story = []

    story.extend(
        [
            paragraph("SECURITY OPERATIONS / HOME LAB", styles["eyebrow"]),
            paragraph("Simulated incident analysis", styles["title"]),
            paragraph(
                "Authentication failures followed by a successful login",
                styles["subtitle"],
            ),
            paragraph(
                "SIMULATION — No real host, user, network packet or account was "
                "monitored. The IP 203.0.113.66 belongs to a range reserved for "
                "documentation and does not identify a real source.",
                styles["callout"],
            ),
            Spacer(1, 8),
        ]
    )

    add_section(story, "1. Executive summary", styles)
    story.append(
        paragraph(
            "The <b>compromised</b> scenario, seed <b>2026</b>, generated 16 synthetic "
            "events. Five login failures for <b>admin</b> came from the same IP "
            "between 12:30 and 12:34 UTC; a success for the same account and source "
            "followed at 12:35 UTC. The detector produced a <b>medium</b> alert for "
            "repeated failures and a <b>high</b> alert for the correlation with the "
            "success. The high alert was recorded as <b>investigating</b>; the medium "
            "one remains <b>open</b>.",
            styles["body"],
        )
    )
    story.append(
        paragraph(
            "Exercise conclusion: the events meet the implemented rules. This does "
            "not prove a real compromise; original sources and context must be "
            "validated before classifying an incident.",
            styles["body"],
        )
    )

    add_section(story, "2. Scope and reproduction", styles)
    story.append(
        make_table(
            [
                ["Item", "Value", "What it represents"],
                ["Scenario / seed", "compromised / 2026", "Reproducible simulator input."],
                ["Events", "16", "10 context events and 6 events in the test sequence."],
                ["Host", "auth-server-01", "Fictitious name included by the generator."],
                ["Run ID", "ac958c2bb9d5494b921fd16a81719abc", "Run recorded in the local SQLite database."],
                ["Response", "None", "No block or automated action was executed."],
            ],
            styles,
            [34 * mm, 59 * mm, 81 * mm],
        )
    )
    story.append(Spacer(1, 7))
    story.append(paragraph("Reproduction without changing the main database:", styles["body"]))
    story.append(
        paragraph(
            "./.venv/bin/python -m soc_lab.simulator --scenario compromised --seed 2026 "
            "--output /tmp/soc-lab-compromised-2026.jsonl<br/>"
            "./.venv/bin/python -m soc_lab.cli --input /tmp/soc-lab-compromised-2026.jsonl "
            "--db /tmp/soc-lab-analysis.sqlite",
            styles["small"],
        )
    )

    add_section(story, "3. Observed timeline", styles)
    story.append(
        make_table(
            [
                ["Time (UTC)", "Synthetic event", "Interpretation"],
                ["12:30", "Failure for admin from 203.0.113.66", "First failure."],
                ["12:31–12:33", "Three more failures for the same account and source", "Count rises to four."],
                ["12:34", "Fifth failure for the same account and source", "The repeated-failures rule reaches the 5/10 min threshold."],
                ["12:35", "Success for admin from the same IP", "The correlation rule finds a success within 5 min."],
            ],
            styles,
            [27 * mm, 74 * mm, 73 * mm],
        )
    )

    add_section(story, "4. Field meanings", styles)
    story.append(
        make_table(
            [
                ["Field", "Example", "Meaning / limits"],
                ["timestamp", "12:30–12:35 UTC", "Fictitious event time; UTC makes it easy to order sources."],
                ["event_type", "authentication", "Classifies the record; it is not a packet capture."],
                ["source_ip", "203.0.113.66", "Synthetic IP. It does not identify a person or a real network."],
                ["username", "admin", "Fictitious target account; it does not reveal who tried to authenticate."],
                ["outcome", "failure / success", "Result produced by the simulator, not confirmed by a real IdP."],
                ["hostname", "auth-server-01", "Fictitious host name assigned to the events."],
                ["event_id", "evt-0011…evt-0016", "Sequential identifier to locate records in the set."],
                ["scenario", "compromised", "Test label; it is not an incident verdict."],
            ],
            styles,
            [29 * mm, 47 * mm, 98 * mm],
        )
    )

    add_section(story, "5. Triggered rules", styles)
    story.append(
        paragraph(
            "<b>multiple_failed_logins — medium.</b> Groups failures by IP and checks "
            "for at least five in a sliding ten-minute window. This rule does not "
            "need to know the user; that is why it is not the rule that states that "
            "admin authenticated successfully.",
            styles["body"],
        )
    )
    story.append(
        paragraph(
            "<b>successful_login_after_failures — high.</b> Correlates by the "
            "IP + user pair. It found five failures for admin between 12:30 and 12:34 "
            "and a success at 12:35. The one-minute gap is within the configured "
            "five-minute window, so the severity was raised.",
            styles["body"],
        )
    )
    story.append(
        paragraph(
            "These are two alerts about the same events, not two independent "
            "occurrences. A more complete SIEM could group both into a single case "
            "to reduce duplication.",
            styles["body"],
        )
    )

    add_section(story, "6. Triage reasoning", styles)
    story.append(
        make_table(
            [
                ["Category", "Analysis"],
                ["Observation", "Five failures and a subsequent success share the same IP and user in the generated set."],
                ["Hypothesis", "If these were real logs, the sequence would justify investigating credential use after repeated attempts."],
                ["Not demonstrated", "There is no evidence of a discovered password, real access, operator identity, MFA or post-login activity."],
                ["Benign alternatives", "Typo before the success, authorized testing, support activity or a shared intermediate address."],
                ["Confidence", "High that the rule matches the synthetic events; no conclusion about a real environment."],
            ],
            styles,
            [37 * mm, 137 * mm],
        )
    )

    add_section(story, "7. Recorded decision and next steps", styles)
    story.append(
        paragraph(
            "The high alert, ID <b>22d19b8ead764333bb959ce0bde6812f</b>, is "
            "<b>investigating</b>. The stored note explicitly marks the simulation "
            "and recommends checking original logs before concluding a compromise. "
            "The medium alert, ID <b>c53808f573ce4dec8578f0303dc0605f</b>, remains "
            "<b>open</b>.",
            styles["body"],
        )
    )
    for step in (
        "Confirm IP, host, user and method in the original logs of the system or identity provider.",
        "Check whether the success and the device/session were expected and review the activity that followed.",
        "Check MFA, source and account history to compare with normal behavior.",
        "If real evidence confirms risk, follow the organization's authorized procedure to protect the account and revoke sessions.",
    ):
        story.append(paragraph(f"• {step}", styles["body"]))

    add_section(story, "8. Limitations and conclusion", styles)
    story.append(
        paragraph(
            "The lab analyzed synthetic JSONL only. It did not read Windows/Linux "
            "logs, did not observe traffic, did not analyze TCP/UDP and did not run "
            "any automated response. The <b>investigating</b> status is part of the "
            "exercise. Never block the documentation IP based on this result; in a "
            "real case, validate the original evidence and follow the authorized process.",
            styles["body"],
        )
    )
    story.append(Spacer(1, 12))
    story.append(
        paragraph(
            "SOC Home Lab teaching report · synthetic scenario · "
            "does not represent a real incident",
            styles["center"],
        )
    )

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    print(f"PDF generated: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the simulated incident report to PDF")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build_report(args.output)


if __name__ == "__main__":
    main()