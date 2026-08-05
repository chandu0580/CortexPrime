"""Generate the project presentation (2 — PPT on the submission checklist).

Ten content slides plus a closing slide. Colours are the running CortexPrime UI
palette — the dark-theme tokens in ``frontend/app/globals.css`` — so the deck
looks like the product it describes.

Content is drawn from what the project actually contains: real detector names,
real line counts, real test numbers, real competitor research. Every figure
quoted here was measured.

    python submission/make_ppt.py
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

import diagrams as dg
from diagrams import (
    ACCENT, ACCENT_2, ACCENT_HI, BG, BORDER_STRONG, DANGER, MUTED, OVERLAY,
    RAISED, SUCCESS, SURFACE, SYMBOL_FONT, TEXT, TEXT_DIM, WARNING, ink_for,
)

OUTPUT = Path(__file__).resolve().parent / "2-CortexPrime-Presentation.pptx"

# ----------------------------------------------------------------------
# Submission details
# ----------------------------------------------------------------------

PROJECT = "CortexPrime"
SUBTITLE = "AI-Native Enterprise Operations Intelligence Platform"
REG_NO = "24BMMCA023"
NAME = "Chandu S"

BODY_FONT = "Segoe UI"
W, H = Inches(13.333), Inches(7.5)   # 16:9


# ======================================================================
# Primitives
# ======================================================================


def _text(frame, runs, *, size=16, colour=TEXT, bold=False, align=PP_ALIGN.LEFT,
          space_after=6):
    """Fill a text frame with lines. ``runs`` is a list of strings or tuples."""
    frame.word_wrap = True
    first = True
    for item in runs:
        text, item_size, item_bold, item_colour = (
            item if isinstance(item, tuple) else (item, size, bold, colour)
        )
        paragraph = frame.paragraphs[0] if first else frame.add_paragraph()
        first = False
        paragraph.alignment = align
        paragraph.space_after = Pt(space_after)
        run = paragraph.add_run()
        run.text = text
        run.font.size = Pt(item_size)
        run.font.bold = item_bold
        run.font.color.rgb = item_colour
        run.font.name = BODY_FONT


def _box(slide, left, top, width, height, *, fill=None, line=None, radius=False):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        left, top, width, height,
    )
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(1)
    shape.shadow.inherit = False
    return shape


def _canvas(presentation):
    """A blank slide painted with the app background."""
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    _box(slide, 0, 0, W, H, fill=BG)
    return slide


def _slide(presentation, title, kicker=None):
    """A content slide with the standard header treatment."""
    slide = _canvas(presentation)
    _box(slide, 0, 0, W, Inches(0.05), fill=ACCENT)

    if kicker:
        box = slide.shapes.add_textbox(Inches(0.7), Inches(0.34), Inches(11), Inches(0.3))
        _text(box.text_frame, [kicker.upper()], size=11, bold=True, colour=ACCENT)

    box = slide.shapes.add_textbox(
        Inches(0.7), Inches(0.6) if kicker else Inches(0.45), Inches(12), Inches(0.7)
    )
    _text(box.text_frame, [title], size=27, bold=True, colour=TEXT)

    _box(slide, Inches(0.72), Inches(1.32), Inches(1.2), Inches(0.035), fill=ACCENT_2)
    return slide


def _footer(slide, number):
    box = slide.shapes.add_textbox(Inches(11.3), Inches(6.98), Inches(1.6), Inches(0.3))
    _text(box.text_frame, [f"{PROJECT}  ·  {number}"], size=9, colour=MUTED,
          align=PP_ALIGN.RIGHT)


def _bullets(slide, items, *, top=1.75, left=0.75, width=11.8, size=16, gap=14):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(4.6))
    frame = box.text_frame
    frame.word_wrap = True
    for index, item in enumerate(items):
        text, detail = item if isinstance(item, tuple) else (item, None)
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        # A heading sits tight against its own detail line; the full gap goes
        # after the pair, so each bullet reads as one block rather than two.
        paragraph.space_after = Pt(3 if detail else gap - 4)
        marker = paragraph.add_run()
        marker.text = "▸  "
        marker.font.size = Pt(size)
        marker.font.bold = True
        marker.font.color.rgb = ACCENT
        marker.font.name = SYMBOL_FONT
        run = paragraph.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bool(detail)
        run.font.color.rgb = TEXT
        run.font.name = BODY_FONT
        if detail:
            sub = frame.add_paragraph()
            sub.space_after = Pt(gap)
            sub_run = sub.add_run()
            sub_run.text = f"     {detail}"
            sub_run.font.size = Pt(size - 3.5)
            sub_run.font.color.rgb = TEXT_DIM
            sub_run.font.name = BODY_FONT


def _cards(slide, cards, *, top=1.9, height=1.35, columns=3, gap=0.3, left_margin=0.75,
           span=None):
    """A grid of titled cards."""
    available = (span or (13.333 - left_margin * 2))
    card_width = (available - gap * (columns - 1)) / columns

    for index, (heading, body) in enumerate(cards):
        row, column = divmod(index, columns)
        left = Inches(left_margin + column * (card_width + gap))
        card_top = Inches(top + row * (height + 0.26))

        _box(slide, left, card_top, Inches(card_width), Inches(height),
             fill=SURFACE, line=BORDER_STRONG, radius=True)
        _box(slide, left, card_top, Inches(0.045), Inches(height), fill=ACCENT)

        box = slide.shapes.add_textbox(
            left + Inches(0.22), card_top + Inches(0.13),
            Inches(card_width - 0.4), Inches(height - 0.2),
        )
        _text(box.text_frame, [
            (heading, 13.5, True, ACCENT),
            (body, 11, False, TEXT_DIM),
        ], space_after=4)


def _stat_row(slide, stats, *, top=5.35, left_margin=0.75, span=None, value_size=30):
    available = span or (13.333 - left_margin * 2)
    width = available / len(stats)
    for index, (value, caption) in enumerate(stats):
        left = Inches(left_margin + index * width)
        box = slide.shapes.add_textbox(left, Inches(top), Inches(width - 0.2), Inches(1.0))
        _text(box.text_frame, [
            (value, value_size, True, ACCENT),
            (caption, 11, False, MUTED),
        ], align=PP_ALIGN.CENTER, space_after=2)


def _flow(slide, steps, *, top=2.6, height=1.0):
    """Horizontal process flow with arrows between boxes."""
    left_margin = 0.75
    available = 13.333 - (left_margin * 2)
    arrow_w = 0.42
    width = (available - arrow_w * (len(steps) - 1)) / len(steps)

    for index, (caption, sub) in enumerate(steps):
        left = Inches(left_margin + index * (width + arrow_w))
        fill = ACCENT if index % 2 == 0 else ACCENT_2
        _box(slide, left, Inches(top), Inches(width), Inches(height), fill=fill, radius=True)
        box = slide.shapes.add_textbox(
            left + Inches(0.08), Inches(top + 0.16), Inches(width - 0.16), Inches(height)
        )
        _text(box.text_frame, [
            (caption, 13, True, ink_for(fill)),
            (sub, 9.5, False, ink_for(fill)),
        ], align=PP_ALIGN.CENTER, space_after=2)

        if index < len(steps) - 1:
            marker = slide.shapes.add_textbox(
                left + Inches(width), Inches(top + 0.24), Inches(arrow_w), Inches(0.5)
            )
            _text(marker.text_frame, ["→"], size=20, colour=ACCENT, align=PP_ALIGN.CENTER)


def _table(slide, headers, rows, *, top=1.9, left=0.75, width=11.8, col_widths=None,
           row_height=0.36):
    shape = slide.shapes.add_table(
        len(rows) + 1, len(headers), Inches(left), Inches(top),
        Inches(width), Inches(0.4 + row_height * len(rows)),
    )
    table = shape.table

    if col_widths:
        total = sum(col_widths)
        for index, share in enumerate(col_widths):
            table.columns[index].width = Emu(int(Inches(width) * share / total))

    for index, header in enumerate(headers):
        cell = table.cell(0, index)
        cell.text = header
        cell.fill.solid()
        cell.fill.fore_color.rgb = ACCENT_2
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        paragraph = cell.text_frame.paragraphs[0]
        paragraph.runs[0].font.size = Pt(12)
        paragraph.runs[0].font.bold = True
        paragraph.runs[0].font.color.rgb = TEXT
        paragraph.runs[0].font.name = BODY_FONT

    for row_index, row in enumerate(rows, start=1):
        for column_index, value in enumerate(row):
            cell = table.cell(row_index, column_index)
            cell.text = str(value)
            cell.fill.solid()
            cell.fill.fore_color.rgb = SURFACE if row_index % 2 else RAISED
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            paragraph = cell.text_frame.paragraphs[0]
            paragraph.runs[0].font.size = Pt(11)
            # The first column names the row — brighten it against the rest.
            paragraph.runs[0].font.color.rgb = TEXT if column_index == 0 else TEXT_DIM
            paragraph.runs[0].font.bold = column_index == 0
            paragraph.runs[0].font.name = BODY_FONT


def _callout(slide, text, *, top=6.05, colour=WARNING, height=0.8):
    _box(slide, Inches(0.75), Inches(top), Inches(11.8), Inches(height),
         fill=RAISED, line=BORDER_STRONG, radius=True)
    _box(slide, Inches(0.75), Inches(top), Inches(0.055), Inches(height), fill=colour)
    box = slide.shapes.add_textbox(
        Inches(1.0), Inches(top + 0.14), Inches(11.4), Inches(height - 0.2)
    )
    _text(box.text_frame, [text], size=13, colour=TEXT)


def _section_label(slide, text, *, top, left, width, colour=ACCENT):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(0.3))
    _text(box.text_frame, [text.upper()], size=11, bold=True, colour=colour)


# ======================================================================
# Slides
# ======================================================================


def build() -> Presentation:
    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = W, H

    # ---- 1. Title ------------------------------------------------------
    slide = _canvas(presentation)
    _box(slide, 0, 0, W, Inches(0.05), fill=ACCENT)
    _box(slide, 0, Inches(6.85), W, Inches(0.65), fill=SURFACE)

    box = slide.shapes.add_textbox(Inches(1.0), Inches(2.25), Inches(11.3), Inches(1.4))
    _text(box.text_frame, [PROJECT], size=60, bold=True, colour=ACCENT)

    box = slide.shapes.add_textbox(Inches(1.05), Inches(3.45), Inches(11.3), Inches(0.6))
    _text(box.text_frame, [SUBTITLE], size=19, colour=TEXT)

    _box(slide, Inches(1.05), Inches(4.2), Inches(2.2), Inches(0.045), fill=ACCENT_2)

    box = slide.shapes.add_textbox(Inches(1.05), Inches(4.6), Inches(11), Inches(0.5))
    _text(box.text_frame,
          ["Detect the problem  ·  Explain the cause  ·  Fix it  ·  Verify"],
          size=15, colour=TEXT_DIM)

    box = slide.shapes.add_textbox(Inches(1.0), Inches(6.98), Inches(11.3), Inches(0.4))
    _text(box.text_frame, [f"{NAME}    ·    {REG_NO}"], size=13, colour=TEXT_DIM)

    # ---- 2. The Problem -------------------------------------------------
    slide = _slide(presentation, "Production breaks. Alerts don't help.", "The Problem")
    dg.split_compare(
        slide,
        "WHAT TODAY'S TOOLS GIVE YOU",
        [
            "\"CPU at 95%\" — a symptom, not a cause",
            "Dozens of alerts for one incident",
            "Logs, metrics and deploys in separate tools",
            "Hours of manual correlation",
            "The fix lives in one engineer's head",
        ],
        "WHAT A TEAM ACTUALLY NEEDS",
        [
            "Which deploy caused it, and which commit",
            "One incident, not forty alerts",
            "Evidence gathered and correlated for you",
            "A specific fix, ready to apply",
            "The knowledge captured in the system",
        ],
        top=1.72, panel_h=4.15,
    )
    _callout(slide,
             "Datadog, Azure SRE Agent and New Relic all diagnose — and all stop there. "
             "Verified from vendor documentation: none of them executes the fix.",
             top=6.05, colour=DANGER)
    _footer(slide, 2)

    # ---- 3. The Loop ----------------------------------------------------
    slide = _slide(presentation, "The CortexPrime Loop", "The Core Idea")
    dg.cycle(slide, [
        ("DETECT", "monitor real systems"),
        ("EXPLAIN", "root cause + evidence"),
        ("PLAN", "a specific fix"),
        ("APPROVE", "human decides"),
        ("EXECUTE", "apply the fix"),
        ("VERIFY", "confirm it worked"),
    ], cy=3.85, centre_text=[("EVERY", 11, True, ACCENT), ("FEATURE", 11, True, ACCENT)])
    _callout(slide,
             "A feature that only raises an alert is incomplete. The loop is the "
             "architecture — not a description of one module.", top=6.05)
    _footer(slide, 3)

    # ---- 4. Architecture -------------------------------------------------
    slide = _slide(presentation, "System Architecture", "Design")
    dg.layer_stack(slide, [
        ("INTERFACES", "Next.js dashboard  ·  REST API  ·  WebSocket", ACCENT_HI),
        ("BOUNDED CONTEXTS",
         "Mission · Evidence · Reasoning · Verification · Execution · Governance", ACCENT),
        ("PLATFORM", "Identity · Hashing · Events · Audit · Context · Architecture Gate",
         ACCENT_2),
        ("CONTRACTS", "Shared vocabulary — depends on nothing", RGBColor(0x33, 0x63, 0x4E)),
        ("CONNECTORS", "Docker · GitHub · GitLab · Jira · Prometheus · PostgreSQL",
         RGBColor(0x25, 0x45, 0x39)),
    ], top=1.75)
    _callout(slide,
             "Dependency direction is enforced automatically — a violation fails the "
             "build, not a code review.", top=6.05)
    _footer(slide, 4)

    # ---- 5. Decision flow -------------------------------------------------
    slide = _slide(presentation, "From Detection to Verified Fix", "How It Works")
    dg.flowchart(slide, top=1.5)
    _footer(slide, 5)

    # ---- 6. Security ------------------------------------------------------
    slide = _slide(presentation, "The Approved Action Is the Executed Action",
                   "Key Contribution")
    _flow(slide, [
        ("STASH", "action + digest"),
        ("RECORD", "digest stored separately"),
        ("APPROVE", "human signs it"),
        ("RE-CHECK", "recompute digest"),
        ("COMPARE", "match or refuse"),
    ], top=1.62, height=0.88)

    box = slide.shapes.add_textbox(Inches(0.75), Inches(2.72), Inches(11.8), Inches(1.2))
    _text(box.text_frame, [
        ("Published penetration testing has defeated human approval in real products by "
         "making what the reviewer SEES differ from what the system EXECUTES. CortexPrime "
         "binds the two cryptographically, in two independent stores — if a single byte "
         "changes after approval, execution refuses and the attempt is audited.",
         13, False, TEXT_DIM),
    ], space_after=6)

    _section_label(slide, "And the record itself cannot be edited", top=3.95, left=0.75,
                   width=11.8)
    dg.hash_chain(slide, top=4.35, compact=True)
    _footer(slide, 6)

    # ---- 7. Detectors ------------------------------------------------------
    slide = _slide(presentation, "Eight Detectors — Each Completing the Loop", "Modules")
    _table(slide,
           ["#", "Detector", "Detects", "Proposed fix"],
           [
               ["1", "Deploy regression", "Error/latency spike after a deploy", "Roll back to last good"],
               ["2", "Docker health", "Crash-loops, OOM kills", "Restart the container"],
               ["3", "Credential expiry", "Tokens nearing expiry", "Alert with renewal steps"],
               ["4", "Vulnerability", "Dependabot security alerts", "Dependency-bump pull request"],
               ["5", "Branch protection", "Missing reviews or CI checks", "Enable minimum protection"],
               ["6", "LLM cost anomaly", "Provider spend spike", "Disable provider temporarily"],
               ["7", "Flaky test", "Intermittently failing tests", "Quarantine and report"],
               ["8", "Alert correlation", "Duplicate alerts across tools", "Merge into one incident"],
           ],
           top=1.72, col_widths=[0.5, 2.6, 4.3, 4.4], row_height=0.42)
    _callout(slide,
             "Every detector was proven against a real external system — a real "
             "crash-looping container, a real Jira ticket, a real database — never a mock alone.",
             top=6.05, colour=SUCCESS)
    _footer(slide, 7)

    # ---- 8. Technology and scale --------------------------------------------
    slide = _slide(presentation, "Technology and Implementation", "Build")
    _cards(slide, [
        ("Frontend", "Next.js 16 · React 19 · Tailwind CSS · TanStack Query"),
        ("Backend", "Python 3.13 · FastAPI · async SQLAlchemy · Uvicorn"),
        ("Database", "PostgreSQL 16 with pgvector · Alembic migrations"),
        ("Infrastructure", "Docker · Redis · RabbitMQ · Prometheus"),
        ("AI Providers", "OpenAI · Anthropic · Google · Azure OpenAI (pluggable)"),
        ("Quality", "pytest · GitHub Actions · architecture fitness functions"),
    ], columns=3, height=1.28, top=1.72)
    _stat_row(slide, [
        ("157K", "lines of code"),
        ("698", "Python modules"),
        ("~3,000", "automated tests"),
        ("17", "architecture decision records"),
        ("8", "detector loops"),
    ], top=5.3, value_size=27)
    _footer(slide, 8)

    # ---- 9. Testing and the architecture gate ---------------------------------
    slide = _slide(presentation, "Testing and Self-Enforcing Architecture",
                   "Quality Assurance")
    _table(slide,
           ["Level", "What it proves", "Count"],
           [
               ["Unit tests", "Individual functions behave correctly", "~2,400"],
               ["Contract tests", "Module boundaries hold", "190"],
               ["Platform tests", "Identity, hashing, events, audit, context", "440"],
               ["Adversarial tests", "Security controls survive deliberate attack", "150"],
               ["Architecture tests", "Every architectural rule catches its own violation", "92"],
               ["Live validation", "Real Docker, real Jira tickets, real database", "Manual"],
           ],
           top=1.72, col_widths=[2.6, 6.5, 1.6], row_height=0.4)
    _stat_row(slide, [
        ("13", "architecture rules in CI"),
        ("752", "modules analysed"),
        ("0", "violations"),
        ("100%", "invariants covered by tests"),
    ], top=4.65, value_size=27)
    _callout(slide,
             "Architectural drift is a build failure, not a code-review argument — each "
             "of the 13 rules is itself tested by deliberately breaking it.",
             top=6.05, colour=SUCCESS)
    _footer(slide, 9)

    # ---- 10. Conclusion and future scope -------------------------------------
    slide = _slide(presentation, "Conclusion and Future Scope", "Summary")

    _section_label(slide, "What this project achieved", top=1.62, left=0.75, width=5.7)
    _bullets(slide, [
        ("The loop is closed", "Eight detectors that explain, fix and verify — not just alert"),
        ("Safety is structural", "Approval gating and cryptographic binding, enforced by CI"),
        ("The architecture defends itself", "13 automated rules keep the design intact"),
        ("Validated against reality", "Real containers, real tickets, real databases"),
    ], top=1.98, left=0.75, width=5.65, size=14, gap=34)

    _box(slide, Inches(6.66), Inches(1.7), Inches(0.012), Inches(3.9), fill=BORDER_STRONG)

    _section_label(slide, "Where it goes next", top=1.62, left=6.95, width=5.6,
                   colour=ACCENT_HI)
    _bullets(slide, [
        ("Open-ended missions", "Any goal in natural language, not ten fixed detectors"),
        ("Tool-selection engine", "Choose which checks to run for an unseen problem"),
        ("Kubernetes support", "Extend container health from Docker to clusters"),
        ("Multi-tenant SaaS", "Serve several organisations from one installation"),
    ], top=1.98, left=6.95, width=5.6, size=14, gap=34)

    _callout(slide,
             "Autonomous operations and human control are not in conflict — the approval "
             "gate is what makes autonomy safe.", top=6.05, colour=SUCCESS)
    _footer(slide, 10)

    # ---- 11. Thank you ---------------------------------------------------------
    slide = _canvas(presentation)
    _box(slide, 0, 0, W, Inches(0.05), fill=ACCENT)

    box = slide.shapes.add_textbox(Inches(1.0), Inches(2.75), Inches(11.3), Inches(1.2))
    _text(box.text_frame, ["Thank You"], size=50, bold=True, colour=ACCENT,
          align=PP_ALIGN.CENTER)
    _box(slide, Inches(6.17), Inches(4.0), Inches(1.0), Inches(0.045), fill=ACCENT_2)
    box = slide.shapes.add_textbox(Inches(1.0), Inches(4.3), Inches(11.3), Inches(0.5))
    _text(box.text_frame, ["Questions?"], size=19, colour=TEXT_DIM, align=PP_ALIGN.CENTER)
    box = slide.shapes.add_textbox(Inches(1.0), Inches(5.5), Inches(11.3), Inches(0.8))
    _text(box.text_frame, [
        (NAME, 17, True, TEXT),
        (REG_NO, 13, False, TEXT_DIM),
    ], align=PP_ALIGN.CENTER, space_after=3)

    return presentation


def main() -> None:
    presentation = build()
    presentation.save(OUTPUT)
    size_kb = OUTPUT.stat().st_size / 1024
    count = len(presentation.slides._sldIdLst)
    print(f"\n  {OUTPUT.name}")
    print(f"  {count} slides, {size_kb:.1f} KB\n")
    print("  Open in PowerPoint and check the layout before presenting.\n")


if __name__ == "__main__":
    main()
