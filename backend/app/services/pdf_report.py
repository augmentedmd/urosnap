from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import Settings, get_settings
from app.models.entities import ProcedureSession, Snapshot
from app.paths import backend_assets_dir

# Mount Sinai primary palette (brand guidelines: Process Cyan, Pantone 233, Pantone 274).
MS_CYAN = colors.HexColor("#00AEEF")
MS_MAGENTA = colors.HexColor("#D80B8C")
MS_NAVY = colors.HexColor("#221F72")
MS_TINT = colors.HexColor("#E6F7FD")

DEFAULT_LOGO_NAME = "mount_sinai_doctors_logo.png"


def format_report_date(value: date | datetime | None) -> str:
    """Nov 12, 2026 — built by hand because %-d is not supported on Windows."""
    if value is None:
        return "—"
    return f"{value:%b} {value.day}, {value.year}"


def custom_logo_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.data_dir / "branding" / "report_logo.png"


def report_logo_path(settings: Settings | None = None) -> Optional[Path]:
    custom = custom_logo_path(settings)
    if custom.exists():
        return custom
    bundled = backend_assets_dir() / DEFAULT_LOGO_NAME
    return bundled if bundled.exists() else None


def _logo_flowable(path: Path, max_w: float, max_h: float) -> Image:
    with PILImage.open(path) as im:
        iw, ih = im.size
    scale = min(max_w / iw, max_h / ih)
    img = Image(str(path), width=iw * scale, height=ih * scale)
    img.hAlign = "LEFT"
    return img


def calculate_grid(images_per_page: int) -> tuple[int, int]:
    """Return (columns, rows) for a given images-per-page density."""
    if images_per_page < 1:
        images_per_page = 1
    if images_per_page > 20:
        images_per_page = 20
    presets = {
        1: (1, 1),
        2: (1, 2),
        3: (1, 3),
        4: (2, 2),
        5: (2, 3),
        6: (2, 3),
        7: (2, 4),
        8: (2, 4),
        9: (3, 3),
        10: (2, 5),
        12: (3, 4),
        15: (3, 5),
        16: (4, 4),
        20: (4, 5),
    }
    if images_per_page in presets:
        return presets[images_per_page]
    cols = math.ceil(math.sqrt(images_per_page))
    rows = math.ceil(images_per_page / cols)
    return cols, rows


def density_warning(images_per_page: int) -> Optional[str]:
    if images_per_page >= 16:
        return "High image density may make photographs unusually small on the page."
    return None


class PdfReportGenerator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def generate(
        self,
        session: ProcedureSession,
        snapshots: list[Snapshot],
        notes: str,
        images_per_page: int,
        output_path: Path,
        include_captions: bool = True,
        include_timestamps: bool = False,
        practice_overrides: Optional[dict] = None,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        practice = {
            "name": self.settings.practice_name,
            "line1": self.settings.practice_address_line1,
            "line2": self.settings.practice_address_line2,
            "phone": self.settings.practice_phone,
        }
        if practice_overrides:
            practice.update({k: v for k, v in practice_overrides.items() if v})

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.65 * inch,
            bottomMargin=0.75 * inch,
            title=f"{session.display_procedure_name} Report",
            author=practice["name"],
        )
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="PracticeName",
                parent=styles["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=13,
                leading=16,
                textColor=MS_NAVY,
                alignment=TA_RIGHT,
                spaceAfter=2,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PracticeSub",
                parent=styles["Normal"],
                fontSize=9.5,
                leading=12,
                alignment=TA_RIGHT,
                textColor=colors.HexColor("#334155"),
            )
        )
        styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=styles["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=17,
                leading=21,
                textColor=MS_NAVY,
                alignment=TA_LEFT,
                spaceBefore=4,
                spaceAfter=8,
            )
        )
        styles.add(
            ParagraphStyle(
                name="SectionHead",
                parent=styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=12,
                textColor=MS_NAVY,
                spaceBefore=14,
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                name="BodyNotes",
                parent=styles["Normal"],
                fontSize=10,
                leading=14,
                alignment=TA_LEFT,
            )
        )
        styles.add(
            ParagraphStyle(
                name="Caption",
                parent=styles["Normal"],
                fontSize=8,
                leading=10,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#475569"),
            )
        )

        usable_width = letter[0] - doc.leftMargin - doc.rightMargin
        story: list = []

        practice_lines = [Paragraph(practice["name"], styles["PracticeName"])]
        for key in ("line1", "line2", "phone"):
            if practice.get(key):
                practice_lines.append(Paragraph(practice[key], styles["PracticeSub"]))
        logo_path = report_logo_path(self.settings)
        logo_w = 1.6 * inch
        logo_cell = _logo_flowable(logo_path, logo_w, 1.05 * inch) if logo_path else ""
        header = Table(
            [[logo_cell, practice_lines]],
            colWidths=[logo_w + 0.2 * inch, usable_width - logo_w - 0.2 * inch],
        )
        header.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(header)
        # Brand rule: cyan and magenta side by side, never overlapping.
        rule = Table([["", ""]], colWidths=[usable_width * 0.62, usable_width * 0.38], rowHeights=[4])
        rule.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), MS_CYAN),
                    ("BACKGROUND", (1, 0), (1, 0), MS_MAGENTA),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(rule)
        story.append(Spacer(1, 10))
        story.append(Paragraph(session.display_procedure_name, styles["ReportTitle"]))

        patient = session.patient
        patient_name = (
            f"{patient.last_name}, {patient.first_name}".strip(", ").strip() or "Unnamed patient"
        )
        dob = patient.date_of_birth
        dob_text = "—" if dob is None or dob.year <= 1900 else format_report_date(dob)
        demo_data = [
            ["Patient Name", patient_name],
            ["Date of Birth", dob_text],
            ["Medical Record Number", patient.medical_record_number or "—"],
            ["Procedure", session.display_procedure_name],
            ["Procedure Date", format_report_date(session.procedure_date)],
            ["Location", session.location or "—"],
        ]
        table = Table(demo_data, colWidths=[2.0 * inch, usable_width - 2.0 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (0, -1), MS_NAVY),
                    ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#0F172A")),
                    ("BACKGROUND", (0, 0), (0, -1), MS_TINT),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#B9E6F8")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B9E6F8")),
                ]
            )
        )
        story.append(table)

        story.append(Paragraph("Notes", styles["SectionHead"]))
        notes_text = (notes or "").strip() or "—"
        # Preserve paragraphs / line breaks
        for block in notes_text.split("\n"):
            safe = (
                block.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                or "&nbsp;"
            )
            story.append(Paragraph(safe, styles["BodyNotes"]))
            story.append(Spacer(1, 4))

        selected = [s for s in snapshots if s.selected]
        selected.sort(key=lambda s: (s.display_order is None, s.display_order or 0, s.sequence_number))

        if selected:
            story.append(Paragraph("Photographs", styles["SectionHead"]))
            cols, rows = calculate_grid(images_per_page)
            usable_height = letter[1] - doc.topMargin - doc.bottomMargin - 0.6 * inch
            cell_w = usable_width / cols
            cell_h = usable_height / rows
            h_pad = 6
            v_pad = 18 if (include_captions or include_timestamps) else 8

            # Rows flow straight after the notes (starting on page 1); each row is its own
            # table so ReportLab moves a whole row to the next page instead of splitting it.
            prepared: list[tuple[Image, str]] = []
            for snap in selected:
                img_path = Path(snap.file_path)
                if not img_path.exists():
                    continue
                with PILImage.open(img_path) as im:
                    iw, ih = im.size
                max_w = max(40.0, float(cell_w) - float(h_pad))
                max_h = max(40.0, float(cell_h) - float(v_pad) - 16.0)
                scale = min(max_w / float(iw), max_h / float(ih))
                draw_w = round(float(iw) * scale, 2)
                draw_h = round(float(ih) * scale, 2)
                img = Image(str(img_path), width=draw_w, height=draw_h)
                img.hAlign = "CENTER"
                caption_parts = []
                if include_timestamps:
                    caption_parts.append(format_report_date(snap.capture_timestamp))
                if include_captions and snap.caption:
                    caption_parts.append(snap.caption)
                prepared.append((img, " — ".join(caption_parts)))

            # Alternate image rows and caption rows for reliable layout sizing
            idx = 0
            while idx < len(prepared):
                chunk = prepared[idx : idx + cols]
                img_row = [item[0] for item in chunk]
                while len(img_row) < cols:
                    img_row.append("")
                img_table = Table([img_row], colWidths=[cell_w] * cols)
                img_table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ]
                    )
                )
                row_flowables: list = [img_table]
                cap_row = []
                for item in chunk:
                    if item[1]:
                        safe_cap = (
                            item[1]
                            .replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                        )
                        cap_row.append(Paragraph(safe_cap, styles["Caption"]))
                    else:
                        cap_row.append("")
                while len(cap_row) < cols:
                    cap_row.append("")
                if any(cap_row):
                    cap_table = Table([cap_row], colWidths=[cell_w] * cols)
                    cap_table.setStyle(
                        TableStyle(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                            ]
                        )
                    )
                    row_flowables.append(cap_table)
                story.append(KeepTogether(row_flowables))
                idx += cols

        def _footer(canvas, doc_):  # type: ignore[no-untyped-def]
            canvas.saveState()
            width = letter[0] - doc_.leftMargin - doc_.rightMargin
            canvas.setFillColor(MS_CYAN)
            canvas.rect(doc_.leftMargin, 0.58 * inch, width * 0.62, 1.5, stroke=0, fill=1)
            canvas.setFillColor(MS_MAGENTA)
            canvas.rect(doc_.leftMargin + width * 0.62, 0.58 * inch, width * 0.38, 1.5, stroke=0, fill=1)
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(MS_NAVY)
            page_num = canvas.getPageNumber()
            canvas.drawCentredString(letter[0] / 2, 0.4 * inch, f"Page {page_num}")
            canvas.drawString(doc_.leftMargin, 0.4 * inch, practice["name"])
            canvas.drawRightString(
                letter[0] - doc_.rightMargin,
                0.4 * inch,
                f"Generated {format_report_date(datetime.now())}",
            )
            canvas.restoreState()

        doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
        return output_path
