from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import Settings, get_settings
from app.models.entities import ProcedureSession, Snapshot


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
        include_timestamps: bool = True,
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
                fontSize=16,
                textColor=colors.HexColor("#0B3A5C"),
                alignment=TA_CENTER,
                spaceAfter=4,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PracticeSub",
                parent=styles["Normal"],
                fontSize=10,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#334155"),
                spaceAfter=2,
            )
        )
        styles.add(
            ParagraphStyle(
                name="SectionHead",
                parent=styles["Heading2"],
                fontSize=12,
                textColor=colors.HexColor("#0B3A5C"),
                spaceBefore=14,
                spaceAfter=8,
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

        story: list = []
        story.append(Paragraph(practice["name"], styles["PracticeName"]))
        story.append(Paragraph(practice["line1"], styles["PracticeSub"]))
        story.append(Paragraph(practice["line2"], styles["PracticeSub"]))
        story.append(Paragraph(practice["phone"], styles["PracticeSub"]))
        story.append(Spacer(1, 8))
        story.append(
            Paragraph(session.display_procedure_name, styles["PracticeName"])
        )
        story.append(Spacer(1, 6))

        patient = session.patient
        patient_name = (
            f"{patient.last_name}, {patient.first_name}".strip(", ").strip() or "Unnamed patient"
        )
        dob = patient.date_of_birth
        dob_text = "—" if dob is None or dob.year <= 1900 else dob.isoformat()
        demo_data = [
            ["Patient Name", patient_name],
            ["Date of Birth", dob_text],
            ["Medical Record Number", patient.medical_record_number or "—"],
            ["Procedure", session.display_procedure_name],
            ["Procedure Date", session.procedure_date.isoformat()],
            [
                "Procedure Time",
                session.procedure_time.strftime("%H:%M") if session.procedure_time else "—",
            ],
            ["Location", session.location or "—"],
            ["Performing Urologist", session.physician or "—"],
        ]
        table = Table(demo_data, colWidths=[2.2 * inch, 4.5 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#CBD5E1")),
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
            story.append(PageBreak())
            story.append(Paragraph("Photographs", styles["SectionHead"]))
            cols, rows = calculate_grid(images_per_page)
            usable_width = letter[0] - doc.leftMargin - doc.rightMargin
            usable_height = letter[1] - doc.topMargin - doc.bottomMargin - 0.6 * inch
            cell_w = usable_width / cols
            cell_h = usable_height / rows
            h_pad = 6
            v_pad = 18 if (include_captions or include_timestamps) else 8

            pages = [
                selected[i : i + images_per_page]
                for i in range(0, len(selected), images_per_page)
            ]
            for page_idx, page_snaps in enumerate(pages):
                if page_idx > 0:
                    story.append(PageBreak())
                    story.append(Paragraph("Photographs (continued)", styles["SectionHead"]))
                # Build image+caption pairs, then place into a grid of Paragraph/Image cells
                prepared: list[tuple[Image, str]] = []
                for snap in page_snaps:
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
                        caption_parts.append(snap.capture_timestamp.strftime("%Y-%m-%d %H:%M:%S"))
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
                    story.append(img_table)
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
                        story.append(cap_table)
                    idx += cols

        def _footer(canvas, doc_):  # type: ignore[no-untyped-def]
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#64748B"))
            page_num = canvas.getPageNumber()
            canvas.drawCentredString(letter[0] / 2, 0.4 * inch, f"Page {page_num}")
            canvas.drawString(
                doc_.leftMargin,
                0.4 * inch,
                f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            )
            canvas.restoreState()

        doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
        return output_path
