from io import BytesIO
from datetime import datetime
import os
from flask import current_app

def create_trade_pdf(trade, tx=None):
    """Generate a refined PDF report for a trade and optional escrow transaction.

    Produces a centered title and a clean tabular layout for main trade particulars.
    Returns a BytesIO buffer containing the PDF data.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
    except Exception:
        raise RuntimeError("Missing reportlab dependency; install reportlab")

    buf = BytesIO()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        alignment=TA_CENTER,
        fontSize=18,
        leading=22,
    )
    normal = styles["Normal"]

    elements = []

    # Optional logo (centered) if present in static/images/logo.png
    try:
        logo_path = os.path.join(current_app.root_path, "static", "images", "logo.png")
    except Exception:
        logo_path = None

    if logo_path and os.path.exists(logo_path):
        try:
            from reportlab.platypus import Image as RLImage
            try:
                from PIL import Image as PILImage
            except Exception:
                PILImage = None

            # Define pleasing maximum dimensions for the logo in the PDF
            max_width = 70 * mm
            max_height = 24 * mm

            if PILImage is not None:
                with PILImage.open(logo_path) as pi:
                    w_px, h_px = pi.size
                    # compute aspect and scale to fit within max box
                    img_ratio = w_px / float(h_px)
                    box_ratio = (max_width / float(max_height))
                    if img_ratio > box_ratio:
                        # wide image: limit by width
                        target_w = max_width
                        target_h = max_width / img_ratio
                    else:
                        # tall image: limit by height
                        target_h = max_height
                        target_w = max_height * img_ratio
            else:
                # Fallback size if Pillow not available
                target_w = max_width
                target_h = None

            if target_h is not None:
                img = RLImage(logo_path, width=target_w, height=target_h)
            else:
                img = RLImage(logo_path, width=target_w)

            img.hAlign = "CENTER"
            elements.append(img)
            elements.append(Spacer(1, 6))
        except Exception:
            # If image fails, continue without it
            pass

    # Centered title
    elements.append(Paragraph("ChainPort - Trade Report", title_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", normal))
    elements.append(Spacer(1, 12))

    # Main trade particulars in a two-column table
    trade_rows = [
        ["Trade ID", str(getattr(trade, "id", "-"))],
        ["Product ID", str(getattr(trade, "product_id", "-"))],
        ["Buyer ID", str(getattr(trade, "buyer_id", "-"))],
        ["Seller ID", str(getattr(trade, "seller_id", "-"))],
        ["Quantity", str(getattr(trade, "quantity", "-"))],
        ["Unit", str(getattr(trade, "unit", "-"))],
        ["Price per unit", str(getattr(trade, "price_per_unit", "-"))],
        ["Total amount", str(getattr(trade, "total_amount", "-"))],
        ["Currency", str(getattr(trade, "currency", "-"))],
        ["Status", str(getattr(trade, "status", "-"))],
    ]

    table = Table(trade_rows, colWidths=[60 * mm, None])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    elements.append(table)
    elements.append(Spacer(1, 12))

    # If there is a transaction, render its details in a small table
    if tx is not None:
        elements.append(Paragraph("Escrow Transaction", styles["Heading3"]))
        tx_rows = [
            ["Transaction ID", str(getattr(tx, "id", "-"))],
            ["Type", str(getattr(tx, "transaction_type", "-"))],
            ["Amount", str(getattr(tx, "amount", "-"))],
        ]
        created = getattr(tx, "created_at", None)
        if created:
            tx_rows.append(["Date", created.strftime("%Y-%m-%d %H:%M:%S")])
        notes = getattr(tx, "notes", None)
        if notes:
            tx_rows.append(["Notes", str(notes)])

        tx_table = Table(tx_rows, colWidths=[60 * mm, None])
        tx_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        elements.append(tx_table)
        elements.append(Spacer(1, 8))

    # Footer note
    elements.append(Paragraph("This is an autogenerated report from ChainPort.", styles["Italic"]))

    doc.build(elements)
    buf.seek(0)
    return buf
