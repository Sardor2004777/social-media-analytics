"""PDF report builder using ReportLab.

Chosen over WeasyPrint because ReportLab is pure-Python — no Cairo/Pango
system deps — so it installs cleanly on Render / Railway / Docker.

The output is a branded multi-page report:
    1. Cover page (gradient-ish background using coloured rectangles)
    2. Executive summary (KPI grid)
    3. Platform breakdown (table)
    4. Sentiment analysis (distribution + top positive/negative samples)
    5. Top posts table

All text is Unicode-safe (Helvetica subset). The workbook is returned as bytes.
"""
from __future__ import annotations

import io
from collections import Counter
from datetime import datetime

from django.db.models import Avg, Count, Sum
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, NextPageTemplate, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

from apps.analytics.models import SentimentLabel, SentimentResult
from apps.collectors.models import Comment
from apps.social.models import ConnectedAccount, Post


BRAND = colors.HexColor("#4f46e5")
BRAND_LIGHT = colors.HexColor("#eef2ff")
BRAND_DARK = colors.HexColor("#312e81")
TEXT = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
BORDER = colors.HexColor("#e2e8f0")

EMERALD = colors.HexColor("#10b981")
AMBER = colors.HexColor("#f59e0b")
ROSE = colors.HexColor("#f43f5e")
SLATE = colors.HexColor("#64748b")


def _styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", parent=base["Title"], fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=TEXT, alignment=TA_LEFT, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=TEXT, alignment=TA_LEFT, spaceBefore=14, spaceAfter=8),
        "h3": ParagraphStyle("h3", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=BRAND_DARK, alignment=TA_LEFT, spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName="Helvetica", fontSize=10, leading=14, textColor=TEXT),
        "muted": ParagraphStyle("muted", parent=base["BodyText"], fontName="Helvetica", fontSize=9, leading=12, textColor=MUTED),
        "cover_title": ParagraphStyle("cov_t", fontName="Helvetica-Bold", fontSize=36, leading=42, textColor=colors.white, alignment=TA_LEFT),
        "cover_sub":   ParagraphStyle("cov_s", fontName="Helvetica", fontSize=14, leading=18, textColor=colors.whitesmoke, alignment=TA_LEFT),
        "cover_small": ParagraphStyle("cov_m", fontName="Helvetica", fontSize=10, leading=14, textColor=colors.lightgrey, alignment=TA_LEFT),
        "small":       ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=10, textColor=MUTED),
    }


def _draw_page_chrome(canvas, doc) -> None:
    """Footer with page number + small branding. Called on every non-cover page."""
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.3)
    canvas.line(20 * mm, 15 * mm, A4[0] - 20 * mm, 15 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 10 * mm, "Social Analytics · diplom loyihasi")
    canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _draw_cover(canvas, doc) -> None:
    """First page — full-bleed brand gradient."""
    w, h = A4
    canvas.saveState()
    # Gradient-ish: stack 4 coloured rectangles top-to-bottom
    stops = [
        (h * 0.75, h,       colors.HexColor("#4f46e5")),
        (h * 0.50, h * 0.75, colors.HexColor("#6366f1")),
        (h * 0.25, h * 0.50, colors.HexColor("#7c3aed")),
        (0,        h * 0.25, colors.HexColor("#1e1b4b")),
    ]
    for (y1, y2, c) in stops:
        canvas.setFillColor(c)
        canvas.rect(0, y1, w, y2 - y1, stroke=0, fill=1)
    # subtle decorative circles
    canvas.setFillColor(colors.white)
    canvas.setFillAlpha(0.08)
    canvas.circle(w * 0.85, h * 0.85, 60 * mm, stroke=0, fill=1)
    canvas.circle(w * 0.15, h * 0.18, 45 * mm, stroke=0, fill=1)
    canvas.setFillAlpha(1)
    canvas.restoreState()


# ---------------------------------------------------------------------------

def build_pdf(user) -> bytes:
    buf = io.BytesIO()
    style = _styles()

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=25 * mm, bottomMargin=22 * mm,
        title=f"Social Analytics — {user.email}",
        author="Social Analytics",
    )

    # Cover uses a full-bleed frame
    cover_frame = Frame(20 * mm, 20 * mm, A4[0] - 40 * mm, A4[1] - 40 * mm, id="cover")
    content_frame = Frame(20 * mm, 22 * mm, A4[0] - 40 * mm, A4[1] - 50 * mm, id="content")

    doc.addPageTemplates([
        PageTemplate(id="cover",   frames=[cover_frame],   onPage=_draw_cover),
        PageTemplate(id="content", frames=[content_frame], onPage=_draw_page_chrome),
    ])

    story = []

    # ---------- Cover ----------
    story.append(Spacer(1, 100 * mm))
    story.append(Paragraph("Social Analytics", style["cover_title"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Umumiy hisobot", style["cover_sub"]))
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph(f"Foydalanuvchi: <b>{_escape(user.email)}</b>", style["cover_small"]))
    story.append(Paragraph(f"Sana: {datetime.now():%Y-%m-%d %H:%M}", style["cover_small"]))

    # Switch to the content page template before forcing a page break.
    story.append(NextPageTemplate("content"))
    story.append(PageBreak())

    # ---------- Executive summary ----------
    story.append(Paragraph("Umumiy ko'rsatkichlar", style["h1"]))
    story.append(Paragraph("Akkauntlar, postlar, kommentlar va sentiment bo'yicha xulosa.", style["muted"]))
    story.append(Spacer(1, 8 * mm))

    accounts = ConnectedAccount.objects.filter(user=user)
    posts = Post.objects.filter(account__user=user)
    comments = Comment.objects.filter(post__account__user=user)
    sentiments = SentimentResult.objects.filter(comment__post__account__user=user)

    avg_eng = posts.aggregate(v=Avg("engagement_rate"))["v"] or 0
    total_likes = posts.aggregate(v=Sum("likes"))["v"] or 0
    total_views = posts.aggregate(v=Sum("views"))["v"] or 0

    pos = sentiments.filter(label=SentimentLabel.POSITIVE).count()
    neu = sentiments.filter(label=SentimentLabel.NEUTRAL).count()
    neg = sentiments.filter(label=SentimentLabel.NEGATIVE).count()
    total_s = max(pos + neu + neg, 1)

    kpi_rows = [
        ["Akkauntlar",           str(accounts.count())],
        ["Jami postlar",         f"{posts.count():,}"],
        ["Jami kommentlar",      f"{comments.count():,}"],
        ["Jami layklar",         f"{total_likes:,}"],
        ["Jami ko'rishlar",      f"{total_views:,}"],
        ["O'rtacha engagement",  f"{avg_eng*100:.2f}%"],
        ["Pozitiv sentiment",    f"{pos*100/total_s:.1f}%"],
        ["Neytral sentiment",    f"{neu*100/total_s:.1f}%"],
        ["Negativ sentiment",    f"{neg*100/total_s:.1f}%"],
    ]
    t = Table(kpi_rows, colWidths=[90 * mm, 60 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME",   (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 10),
        ("TEXTCOLOR",  (0,0), (0,-1), MUTED),
        ("TEXTCOLOR",  (1,0), (1,-1), TEXT),
        ("FONTNAME",   (1,0), (1,-1), "Helvetica-Bold"),
        ("ALIGN",      (1,0), (1,-1), "RIGHT"),
        ("LINEBELOW",  (0,0), (-1,-1), 0.3, BORDER),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t)

    # ---------- Platform breakdown ----------
    story.append(PageBreak())
    story.append(Paragraph("Platforma bo'yicha", style["h1"]))
    story.append(Paragraph("Har bir ulangan akkaunt bo'yicha metrikalar.", style["muted"]))
    story.append(Spacer(1, 8 * mm))

    rows = [["Platforma", "Handle", "Obunachilar", "Postlar", "Jami layk", "Avg eng."]]
    platform_qs = (
        accounts.annotate(p=Count("posts"), l=Sum("posts__likes"), e=Avg("posts__engagement_rate"))
        .order_by("platform")
    )
    for a in platform_qs:
        rows.append([
            a.get_platform_display(),
            f"@{a.handle}"[:32],
            f"{a.follower_count:,}",
            f"{a.p or 0:,}",
            f"{a.l or 0:,}",
            f"{(a.e or 0)*100:.2f}%",
        ])
    if len(rows) == 1:
        rows.append(["—", "Hali akkaunt yo'q", "", "", "", ""])

    t = Table(rows, colWidths=[28 * mm, 38 * mm, 24 * mm, 20 * mm, 24 * mm, 24 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), BRAND),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",   (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("ALIGN",      (2,1), (-1,-1), "RIGHT"),
        ("ALIGN",      (0,0), (-1,0), "LEFT"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, BRAND_LIGHT]),
        ("LINEBELOW",  (0,0), (-1,-1), 0.3, BORDER),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t)

    # ---------- Sentiment ----------
    story.append(PageBreak())
    story.append(Paragraph("Sentiment tahlili", style["h1"]))
    story.append(Paragraph(f"Jami {sentiments.count():,} komment tahlil qilindi.", style["muted"]))
    story.append(Spacer(1, 6 * mm))

    sent_rows = [
        ["Pozitiv", f"{pos:,}", f"{pos*100/total_s:.1f}%"],
        ["Neytral", f"{neu:,}", f"{neu*100/total_s:.1f}%"],
        ["Negativ", f"{neg:,}", f"{neg*100/total_s:.1f}%"],
    ]
    t = Table(sent_rows, colWidths=[50 * mm, 40 * mm, 40 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME",   (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 10),
        ("TEXTCOLOR",  (0,0), (0,0), EMERALD),
        ("TEXTCOLOR",  (0,1), (0,1), SLATE),
        ("TEXTCOLOR",  (0,2), (0,2), ROSE),
        ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
        ("ALIGN",      (1,0), (-1,-1), "RIGHT"),
        ("LINEBELOW",  (0,0), (-1,-1), 0.3, BORDER),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t)

    # Top positive
    story.append(Paragraph("Eng pozitiv kommentlar", style["h3"]))
    for r in sentiments.filter(label=SentimentLabel.POSITIVE).order_by("-score").select_related("comment", "comment__post__account")[:5]:
        story.append(Paragraph(
            f"<b>[{r.comment.language.upper()} · {r.comment.post.account.platform}]</b> "
            f"“{_escape(r.comment.body)}” — <i>@{_escape(r.comment.author_handle)}</i>",
            style["body"]
        ))
        story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Eng negativ kommentlar", style["h3"]))
    for r in sentiments.filter(label=SentimentLabel.NEGATIVE).order_by("-score").select_related("comment", "comment__post__account")[:5]:
        story.append(Paragraph(
            f"<b>[{r.comment.language.upper()} · {r.comment.post.account.platform}]</b> "
            f"“{_escape(r.comment.body)}” — <i>@{_escape(r.comment.author_handle)}</i>",
            style["body"]
        ))
        story.append(Spacer(1, 2 * mm))

    # ---------- Top posts ----------
    story.append(PageBreak())
    story.append(Paragraph("Eng yaxshi postlar", style["h1"]))
    story.append(Paragraph("Layklar bo'yicha tartiblangan top 15.", style["muted"]))
    story.append(Spacer(1, 6 * mm))

    head = ["#", "Pl.", "Caption", "Layk", "Ko'r.", "Eng. %"]
    rows = [head]
    for i, p in enumerate(posts.select_related("account").order_by("-likes")[:15], start=1):
        rows.append([
            str(i),
            p.account.platform[:3],
            _escape((p.caption or "—")[:55]),
            f"{p.likes:,}",
            f"{p.views:,}",
            f"{p.engagement_rate*100:.2f}%",
        ])
    if len(rows) == 1:
        rows.append(["—", "—", "Hali postlar yo'q", "", "", ""])

    t = Table(rows, colWidths=[10 * mm, 12 * mm, 80 * mm, 22 * mm, 22 * mm, 22 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), BRAND),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("ALIGN",      (3,1), (-1,-1), "RIGHT"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, BRAND_LIGHT]),
        ("LINEBELOW",  (0,0), (-1,-1), 0.3, BORDER),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t)

    story.append(Spacer(1, 12 * mm))
    story.append(Paragraph(
        f"Avtomatik ravishda yaratilgan · {datetime.now():%Y-%m-%d %H:%M}",
        style["small"]
    ))

    doc.build(story)
    return buf.getvalue()


def _escape(s: str) -> str:
    """Escape HTML-significant chars for ReportLab's paragraph parser."""
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
