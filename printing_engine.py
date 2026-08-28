# printing_engine.py
import os
import sys
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import win32print
import win32ui
from PIL import ImageWin

# ReportLab for A4 Invoice and Daily Sales Audit Reports
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def get_image_path():
    candidates = ["YOMES.png", "YOMES.jpeg", "YOMES.jpg", "logo.png", "logo.jpeg", "logo.jpg"]
    for c in candidates:
        if hasattr(sys, '_MEIPASS'):
            p = os.path.join(sys._MEIPASS, c)
            if os.path.exists(p):
                return p
        if os.path.exists(c):
            return c
    return None


# =============================================================================
# 1. DIRECT GRAPHICAL THERMAL SLIP PRINTING (WITH LOGO, LOCATION & PHONE)
# =============================================================================
def print_thermal_receipt_direct(receipt_no, date_str, cart_items, total, paid, balance, customer_name, change=0.0):
    """
    Renders an 80mm thermal receipt directly as a monochrome bitmap image
    and sends it straight to the default Windows POS printer.
    """
    # 80mm standard width at 203 DPI = 576 pixels printable width
    width = 576

    # Dynamically estimate image height based on content
    base_height = 320
    items_height = len(cart_items) * 36
    extra_height = 80 if (change > 0 or balance > 0) else 40
    height = base_height + items_height + extra_height

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # Standard Windows Truetype Fonts
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 24)
        font_bold = ImageFont.truetype("arialbd.ttf", 18)
        font_regular = ImageFont.truetype("arial.ttf", 17)
        font_small = ImageFont.truetype("arial.ttf", 15)
    except Exception:
        font_title = font_bold = font_regular = font_small = ImageFont.load_default()

    y = 10

    # 1. Draw Top Logo
    img_path = get_image_path()
    if img_path and os.path.exists(img_path):
        try:
            logo = Image.open(img_path).convert("RGBA")
            logo_w = 90
            logo_h = int(logo.height * (logo_w / logo.width))
            logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)

            # Center logo
            logo_x = (width - logo_w) // 2
            img.paste(logo, (logo_x, y), mask=logo)
            y += logo_h + 10
        except Exception:
            pass

    # 2. Header & Store Info
    draw.text((width // 2, y), "YOMES ELECTRICAL & HOME SOLUTION", fill="black", font=font_title, anchor="mt")
    y += 28
    draw.text((width // 2, y), "Wholesale & Retail Electrical Supplies", fill="black", font=font_small, anchor="mt")
    y += 20
    draw.text((width // 2, y), "Location: Pokuase  |  Tel: +233 55 840 5048", fill="black", font=font_bold, anchor="mt")
    y += 24
    draw.text((width // 2, y), f"Rec: {receipt_no}  |  {date_str}", fill="black", font=font_small, anchor="mt")
    y += 20
    draw.text((width // 2, y), f"Customer: {customer_name}", fill="black", font=font_small, anchor="mt")
    y += 24

    # 3. Table Headers
    draw.line([(15, y), (width - 15, y)], fill="black", width=2)
    y += 6
    draw.text((15, y), "Item Description", fill="black", font=font_bold)
    draw.text((320, y), "Qty", fill="black", font=font_bold, anchor="mt")
    draw.text((420, y), "Price", fill="black", font=font_bold, anchor="mt")
    draw.text((width - 15, y), "Total", fill="black", font=font_bold, anchor="ra")
    y += 24
    draw.line([(15, y), (width - 15, y)], fill="black", width=1)
    y += 10

    # 4. Item Rows
    for it in cart_items:
        name = it['name'][:22]
        qty_str = f"{it['qty']:.0f}" if it['qty'].is_integer() else f"{it['qty']:.1f}"
        price_str = f"{it['selling_price']:.2f}"
        tot_str = f"{it['line_total']:.2f}"

        draw.text((15, y), name, fill="black", font=font_regular)
        draw.text((320, y), qty_str, fill="black", font=font_regular, anchor="mt")
        draw.text((420, y), price_str, fill="black", font=font_regular, anchor="mt")
        draw.text((width - 15, y), tot_str, fill="black", font=font_regular, anchor="ra")
        y += 26

    # 5. Financial Totals
    y += 4
    draw.line([(15, y), (width - 15, y)], fill="black", width=2)
    y += 8

    draw.text((320, y), "Gross Total:", fill="black", font=font_bold, anchor="ra")
    draw.text((width - 15, y), f"GHS {total:.2f}", fill="black", font=font_bold, anchor="ra")
    y += 24

    draw.text((320, y), "Amount Paid:", fill="black", font=font_regular, anchor="ra")
    draw.text((width - 15, y), f"GHS {paid:.2f}", fill="black", font=font_regular, anchor="ra")
    y += 22

    if change > 0:
        draw.text((320, y), "Change Returned:", fill="black", font=font_bold, anchor="ra")
        draw.text((width - 15, y), f"GHS {change:.2f}", fill="black", font=font_bold, anchor="ra")
        y += 22

    if balance > 0:
        draw.text((320, y), "Debt Balance:", fill="black", font=font_bold, anchor="ra")
        draw.text((width - 15, y), f"GHS {balance:.2f}", fill="black", font=font_bold, anchor="ra")
        y += 22

    # 6. Footer
    y += 6
    draw.line([(15, y), (width - 15, y)], fill="black", width=1)
    y += 10
    draw.text((width // 2, y), "Thank you for your business!", fill="black", font=font_bold, anchor="mt")
    y += 20
    draw.text((width // 2, y), "Goods sold in good condition are not returnable.", fill="black", font=font_small,
              anchor="mt")
    y += 25

    # Crop image to exact used height
    final_img = img.crop((0, 0, width, y))

    # Send directly to the Windows Default Printer
    send_image_to_printer(final_img)


def send_image_to_printer(pil_image):
    """Prints a PIL Image directly to the Windows Default Printer using win32ui."""
    printer_name = win32print.GetDefaultPrinter()

    hDC = win32ui.CreateDC()
    hDC.CreatePrinterDC(printer_name)
    hDC.StartDoc("YOMES POS Receipt")
    hDC.StartPage()

    dib = ImageWin.Dib(pil_image)
    printable_width = hDC.GetDeviceCaps(8)  # HORZRES
    scale_factor = printable_width / pil_image.width
    dest_w = int(pil_image.width * scale_factor)
    dest_h = int(pil_image.height * scale_factor)

    dib.draw(hDC.GetHandleOutput(), (0, 0, dest_w, dest_h))

    hDC.EndPage()
    hDC.EndDoc()
    hDC.DeleteDC()


# =============================================================================
# 2. A4 OFFICIAL INVOICE (PDF)
# =============================================================================
def generate_a4_invoice_pdf(filename, receipt_no, date_str, cart_items, total, paid, balance, customer_info,
                            change=0.0):
    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1E3A8A"),
        spaceAfter=2
    )

    img_p = get_image_path()
    if img_p:
        try:
            logo = RLImage(img_p, width=65, height=65)
            header_table = Table([[logo, [
                Paragraph("<b>YOMES ELECTRICAL & HOME SOLUTION</b>", title_style),
                Paragraph("Wholesale & Retail Electrical Supplies | Pokuase | Tel: +233 55 840 5048", styles['Normal'])
            ]]], colWidths=[75, 445])
            header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
            elements.append(header_table)
        except Exception:
            elements.append(Paragraph("YOMES ELECTRICAL & HOME SOLUTION", title_style))
    else:
        elements.append(Paragraph("YOMES ELECTRICAL & HOME SOLUTION", title_style))

    elements.append(Spacer(1, 15))

    cust_name = customer_info['name'] if customer_info else "Walk-in Customer"
    cust_phone = customer_info['phone'] if customer_info else "N/A"
    cust_addr = customer_info['address'] if customer_info else "N/A"

    info_data = [
        [Paragraph(f"<b>Invoice To:</b> {cust_name}", styles['Normal']),
         Paragraph(f"<b>Invoice No:</b> {receipt_no}", styles['Normal'])],
        [Paragraph(f"<b>Phone:</b> {cust_phone}", styles['Normal']),
         Paragraph(f"<b>Date:</b> {date_str}", styles['Normal'])],
        [Paragraph(f"<b>Address:</b> {cust_addr}", styles['Normal']),
         Paragraph("<b>Status:</b> Official Bill", styles['Normal'])]
    ]
    info_table = Table(info_data, colWidths=[270, 250])
    info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))

    table_data = [["#", "Item Description", "Qty", "Unit Price (GHS)", "Total (GHS)"]]
    for idx, it in enumerate(cart_items, start=1):
        table_data.append([
            str(idx),
            it['name'],
            f"{it['qty']:.0f}" if it['qty'].is_integer() else f"{it['qty']:.1f}",
            f"{it['selling_price']:.2f}",
            f"{it['line_total']:.2f}"
        ])

    table_data.append(["", "", "", "Total Gross Amount:", f"GHS {total:.2f}"])
    table_data.append(["", "", "", "Amount Tendered / Paid:", f"GHS {paid:.2f}"])

    if change > 0:
        table_data.append(["", "", "", "Customer Change:", f"GHS {change:.2f}"])
    if balance > 0:
        table_data.append(["", "", "", "Outstanding Balance (Debt):", f"GHS {balance:.2f}"])

    item_table = Table(table_data, colWidths=[30, 250, 50, 110, 80])
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2563EB")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -3 if (change > 0 or balance > 0) else -2), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('FONTNAME', (3, -3), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (3, -3), (-1, -1), colors.HexColor("#F3F4F6"))
    ]))
    elements.append(item_table)
    elements.append(Spacer(1, 25))
    elements.append(
        Paragraph("<i>Thank you for your business! All warranty items are subject to manufacturer terms.</i>",
                  styles['Normal']))

    doc.build(elements)


# =============================================================================
# 3. DAILY SALES REPORT (PDF)
# =============================================================================
def generate_daily_sales_pdf_report(filename, query_date, sales_list, summary_stats):
    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    img_p = get_image_path()
    if img_p:
        try:
            logo = RLImage(img_p, width=45, height=45)
            header_table = Table([[logo, [
                Paragraph("<b>YOMES ELECTRICAL - DAILY SALES AUDIT</b>", styles['Heading1']),
                Paragraph(f"<b>Pokuase Branch</b> | Tel: +233 55 840 5048 | Audit Date: {query_date}", styles['Normal'])
            ]]], colWidths=[55, 480])
            header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
            elements.append(header_table)
        except Exception:
            elements.append(Paragraph("<b>YOMES ELECTRICAL - DAILY SALES AUDIT</b>", styles['Heading1']))
    else:
        elements.append(Paragraph("<b>YOMES ELECTRICAL - DAILY SALES AUDIT</b>", styles['Heading1']))

    elements.append(Spacer(1, 10))

    data = [["Time", "Receipt No", "Customer", "Method", "Total (GHS)", "Paid (GHS)", "Bal (GHS)", "Cashier"]]
    for s in sales_list:
        time_part = s['sale_date'].split()[1][:5] if ' ' in s['sale_date'] else s['sale_date']
        data.append([
            time_part,
            s['receipt_no'],
            (s['customer_name'] or "Walk-in")[:16],
            s['payment_method'],
            f"{s['total_amount']:.2f}",
            f"{s['amount_paid']:.2f}",
            f"{s['balance_due']:.2f}",
            s['cashier_name'] or "Staff"
        ])

    data.append(["", "", "", "SUMMARY TOTALS:",
                 f"{summary_stats['total_revenue']:.2f}",
                 f"{summary_stats['total_paid']:.2f}",
                 f"{summary_stats['total_balance']:.2f}", ""])

    tv_table = Table(data, colWidths=[40, 95, 100, 60, 75, 75, 60, 60])
    tv_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E5E7EB")),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4)
    ]))
    elements.append(tv_table)
    doc.build(elements)