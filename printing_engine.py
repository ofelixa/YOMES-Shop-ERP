# printing_engine.py
import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

COMPANY_NAME = "YOMES ELECTRICAL & HOME SOLUTION"
COMPANY_PHONE = "+233 00 000 0000"
COMPANY_ADDR = "Accra, Ghana"
CURRENCY = "GHS"


def generate_thermal_slip_text(receipt_no, date_str, items, total, paid, balance, customer_name="Walk-in Customer",
                               payment_type="CASH"):
    width = 32
    slip = []
    slip.append(COMPANY_NAME.center(width))
    slip.append(COMPANY_ADDR.center(width))
    slip.append(COMPANY_PHONE.center(width))
    slip.append("-" * width)
    slip.append(f"Receipt: {receipt_no}")
    slip.append(f"Date: {date_str}")
    slip.append(f"Customer: {customer_name[:16]}")
    slip.append(f"Payment: {payment_type}")
    slip.append("-" * width)
    slip.append(f"{'Item':<16}{'Qty':<4}{'Total':>12}")
    slip.append("-" * width)

    for it in items:
        name = it['name'][:15]
        qty = str(it['qty'])
        total_str = f"{CURRENCY} {it['line_total']:.2f}"
        slip.append(f"{name:<16}{qty:<4}{total_str:>12}")

    slip.append("-" * width)
    slip.append(f"{'Total:':<16}{f'{CURRENCY} {total:.2f}':>16}")
    slip.append(f"{'Paid:':<16}{f'{CURRENCY} {paid:.2f}':>16}")
    if balance > 0:
        slip.append(f"{'Balance Due:':<16}{f'{CURRENCY} {balance:.2f}':>16}")
    slip.append("=" * width)
    slip.append("Thank you for your business!".center(width))
    slip.append("Goods sold are not returnable.".center(width))

    return "\n".join(slip)


def generate_a4_invoice_pdf(file_path, receipt_no, date_str, items, total, paid, balance, customer_data=None):
    doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()
    meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontSize=9, leading=12)

    header_data = [
        [
            Paragraph(f"<b>{COMPANY_NAME}</b><br/>{COMPANY_ADDR}<br/>Tel: {COMPANY_PHONE}", meta_style),
            Paragraph(f"<b>OFFICIAL INVOICE / RECEIPT</b><br/><b>No:</b> {receipt_no}<br/><b>Date:</b> {date_str}",
                      meta_style)
        ]
    ]
    t_header = Table(header_data, colWidths=[300, 220])
    t_header.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(t_header)
    story.append(Spacer(1, 15))

    cust_name = customer_data.get('name', 'Walk-in Customer') if customer_data else 'Walk-in Customer'
    cust_phone = customer_data.get('phone', 'N/A') if customer_data else 'N/A'
    cust_address = customer_data.get('address', 'N/A') if customer_data else 'N/A'

    cust_box = [
        [Paragraph(f"<b>Billed To:</b> {cust_name}", meta_style), Paragraph(f"<b>Phone:</b> {cust_phone}", meta_style)],
        [Paragraph(f"<b>Address:</b> {cust_address}", meta_style),
         Paragraph(f"<b>Account Status:</b> Internal Record", meta_style)]
    ]
    t_cust = Table(cust_box, colWidths=[260, 260])
    t_cust.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_cust)
    story.append(Spacer(1, 15))

    table_rows = [["#", "Item Description", "Qty", f"Unit Price ({CURRENCY})", f"Total ({CURRENCY})"]]
    for idx, item in enumerate(items, 1):
        table_rows.append([
            str(idx),
            item['name'],
            str(item['qty']),
            f"{item['selling_price']:.2f}",
            f"{item['line_total']:.2f}"
        ])

    t_items = Table(table_rows, colWidths=[30, 270, 50, 85, 85])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
    ]))
    story.append(t_items)
    story.append(Spacer(1, 15))

    summary_data = [
        ["Subtotal:", f"{CURRENCY} {total:.2f}"],
        ["Amount Paid:", f"{CURRENCY} {paid:.2f}"],
        ["Balance Due / Outstanding:", f"{CURRENCY} {balance:.2f}"]
    ]
    t_summary = Table(summary_data, colWidths=[150, 100])
    t_summary.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))

    outer_summary = Table([["", t_summary]], colWidths=[270, 250])
    story.append(outer_summary)

    doc.build(story)
    return file_path


def generate_daily_sales_pdf_report(file_path, report_date, sales_rows, summary_stats):
    doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20,
                                 textColor=colors.HexColor("#1E293B"))
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=9, leading=13)

    story.append(Paragraph(f"<b>{COMPANY_NAME}</b>", title_style))
    story.append(Paragraph(f"Daily Sales Audit Report | Date: <b>{report_date}</b>", meta_style))
    story.append(Spacer(1, 10))

    # Summary Statistics Box
    sum_data = [
        [
            Paragraph(f"<b>Total Orders:</b> {summary_stats['count']}", meta_style),
            Paragraph(f"<b>Gross Revenue:</b> {CURRENCY} {summary_stats['total_revenue']:.2f}", meta_style),
            Paragraph(f"<b>Total Paid:</b> {CURRENCY} {summary_stats['total_paid']:.2f}", meta_style),
            Paragraph(f"<b>Credit / Balance Due:</b> {CURRENCY} {summary_stats['total_balance']:.2f}", meta_style)
        ]
    ]
    t_sum = Table(sum_data, colWidths=[130, 135, 135, 135])
    t_sum.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_sum)
    story.append(Spacer(1, 15))

    # Table breakdown
    table_rows = [
        ["Time", "Receipt No", "Customer", "Method", f"Total ({CURRENCY})", f"Paid ({CURRENCY})", f"Bal ({CURRENCY})",
         "Cashier"]]
    for r in sales_rows:
        time_part = r['sale_date'].split()[1][:5] if ' ' in r['sale_date'] else r['sale_date']
        table_rows.append([
            time_part,
            r['receipt_no'],
            (r['customer_name'] or "Walk-in")[:15],
            r['payment_method'],
            f"{r['total_amount']:.2f}",
            f"{r['amount_paid']:.2f}",
            f"{r['balance_due']:.2f}",
            r['cashier_name'][:12]
        ])

    t_sales = Table(table_rows, colWidths=[40, 95, 95, 60, 65, 65, 55, 60])
    t_sales.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('ALIGN', (4, 1), (6, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_sales)

    doc.build(story)
    return file_path