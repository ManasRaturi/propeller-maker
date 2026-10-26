"""Print layout and vector mathematics for the portable study-guide generator."""

from html import unescape
from pathlib import Path
import re

from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
INK = colors.HexColor("#171C1D")
MUTED = colors.HexColor("#536064")
TEAL = colors.HexColor("#1B6C80")
PALE = colors.HexColor("#F1F5F5")
RULE = colors.HexColor("#DCE3E4")
WIDTH = A4[0] - 96
CHECKED_TEXT = []
EQUATIONS = []


def setup_fonts():
    folder = ROOT / "ui" / "assets" / "fonts"
    for name, filename in [("Plex", "IBMPlexSans-Regular.ttf"),
                           ("PlexBold", "IBMPlexSans-SemiBold.ttf"),
                           ("PlexMono", "IBMPlexMono-Regular.ttf")]:
        pdfmetrics.registerFont(TTFont(name, str(folder / filename)))
    pdfmetrics.registerFontFamily("Plex", normal="Plex", bold="PlexBold",
                                  italic="Plex", boldItalic="PlexBold")


def styles():
    base = dict(fontName="Plex", fontSize=10.5, leading=15.2, textColor=INK,
                spaceAfter=8, allowWidows=0, allowOrphans=0)
    return {
        "body": ParagraphStyle("Body", **base),
        "small": ParagraphStyle("Small", fontName="Plex", fontSize=9, leading=12.5,
                                textColor=MUTED, spaceAfter=7),
        "chapter": ParagraphStyle("Chapter", fontName="PlexBold", fontSize=23,
                                  leading=28, textColor=INK, spaceAfter=12,
                                  keepWithNext=True),
        "section": ParagraphStyle("Section", fontName="PlexBold", fontSize=12,
                                  leading=16, textColor=TEAL, spaceBefore=9,
                                  spaceAfter=6, keepWithNext=True),
        "cover": ParagraphStyle("Cover", fontName="PlexBold", fontSize=33,
                                leading=37, textColor=INK, spaceAfter=14),
        "deck": ParagraphStyle("Deck", fontName="Plex", fontSize=15,
                               leading=21, textColor=MUTED, spaceAfter=16),
        "cell": ParagraphStyle("Cell", fontName="Plex", fontSize=9.3,
                               leading=12.6, textColor=INK),
        "head": ParagraphStyle("Head", fontName="PlexBold", fontSize=9.3,
                               leading=12.6, textColor=TEAL),
        "code": ParagraphStyle("Code", fontName="PlexMono", fontSize=8.7,
                               leading=13, textColor=INK, backColor=PALE,
                               borderPadding=8, spaceBefore=4, spaceAfter=10),
    }


def paragraph(text, style):
    CHECKED_TEXT.append((unescape(re.sub(r"<[^>]+>", "", text)), style.fontName))
    return Paragraph(text, style)


class Equation(Flowable):
    """MathText outlines become PDF paths, so every math glyph is self-contained.

    Equations are never passed to ReportLab's paragraph parser as raw LaTeX.
    The printed width is checked, rather than silently shrinking small type.
    """
    def __init__(self, expression, size=14, width=WIDTH, boxed=True):
        super().__init__()
        self.expression = expression
        self.path = TextPath((0, 0), "$" + expression + "$", size=size,
                             usetex=False)
        self.bounds = self.path.get_extents()
        self.boxed = boxed
        padding = 12 if boxed else 2
        if self.bounds.width > width - padding * 2:
            raise ValueError(f"Split this equation into shorter lines: {expression}")
        self.padding = padding
        self.width = width
        self.height = self.bounds.height + padding * 2
        self.spaceBefore = 3
        self.spaceAfter = 8
        EQUATIONS.append(expression)

    def draw(self):
        c = self.canv
        c.saveState()
        if self.boxed:
            c.setFillColor(PALE)
            c.roundRect(0, 0, self.width, self.height, 4, stroke=0, fill=1)
        c.translate(self.padding - self.bounds.x0, self.padding - self.bounds.y0)
        c.setFillColor(INK)
        path = c.beginPath()
        last = (0, 0)
        for verts, code in self.path.iter_segments(curves=True, simplify=False):
            if code == MplPath.MOVETO:
                path.moveTo(*verts)
                last = tuple(verts)
            elif code == MplPath.LINETO:
                path.lineTo(*verts)
                last = tuple(verts)
            elif code == MplPath.CURVE3:
                control, end = verts[:2], verts[2:]
                first = [last[i] + 2 / 3 * (control[i] - last[i]) for i in (0, 1)]
                second = [end[i] + 2 / 3 * (control[i] - end[i]) for i in (0, 1)]
                path.curveTo(*first, *second, *end)
                last = tuple(end)
            elif code == MplPath.CURVE4:
                path.curveTo(*verts)
                last = tuple(verts[-2:])
            elif code == MplPath.CLOSEPOLY:
                path.close()
        c.drawPath(path, stroke=0, fill=1)
        c.restoreState()


def table(rows, widths, sheet, header=True):
    data = []
    for i, row in enumerate(rows):
        style = sheet["head"] if header and i == 0 else sheet["cell"]
        data.append([cell if isinstance(cell, Flowable) else paragraph(str(cell), style)
                     for cell in row])
    result = Table(data, colWidths=widths, repeatRows=int(header), hAlign="LEFT")
    result.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Plex"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, 0), .7, RULE),
        ("LINEBELOW", (0, 1), (-1, -1), .35, RULE),
    ]))
    result.spaceAfter = 10
    return result


def verify_text_glyphs():
    missing = set()
    for text, name in CHECKED_TEXT:
        available = pdfmetrics.getFont(name).face.charToGlyph
        for char in text:
            if not char.isspace() and ord(char) not in available:
                missing.add((name, f"U+{ord(char):04X}", char))
    if missing:
        raise ValueError(f"Missing embedded-font glyphs: {sorted(missing)}")
    return {"checked_text_blocks": len(CHECKED_TEXT), "missing_glyphs": [],
            "vector_equations_and_symbols": len(EQUATIONS)}


class StudyDoc(SimpleDocTemplate):
    """Bookmarks and clickable chapter destinations in a normal PDF canvas."""
    def __init__(self, path, chapters):
        super().__init__(str(path), pagesize=A4, leftMargin=48, rightMargin=48,
                         topMargin=55, bottomMargin=47,
                         title="Propeller Maker - A Practical Study Guide",
                         author="Propeller Maker", subject="Geometry, aerodynamics and CAD, explained step by step")
        self.chapters = chapters
        self.chapter_pages = []

    def afterFlowable(self, flowable):
        if hasattr(flowable, "chapter_id"):
            key = flowable.chapter_id
            self.canv.bookmarkPage(key)
            title = getattr(flowable, "chapter_title", flowable.getPlainText())
            self.canv.addOutlineEntry(title, key, level=0)
            self.chapter_pages.append({"id": key, "page": self.page,
                                       "title": title})

    def decorate(self, c, doc):
        c.saveState()
        c.setFont("Plex", 8.5)
        c.setFillColor(MUTED)
        c.drawString(48, A4[1] - 31, "Propeller Maker / Study guide")
        c.drawRightString(A4[0] - 48, A4[1] - 31, "Concepts + current implementation")
        c.setStrokeColor(RULE)
        c.setLineWidth(.5)
        c.line(48, 38, A4[0] - 48, 38)
        c.drawString(48, 24, "Clockwise, viewed from +Z toward -Z")
        c.drawRightString(A4[0] - 48, 24, f"{doc.page} / {self.chapters}")
        c.restoreState()
