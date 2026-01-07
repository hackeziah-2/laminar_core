# from reportlab.lib.pagesizes import A4
# from reportlab.lib import colors
# from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
# from io import BytesIO

# def generate_pdf_report(title: str, headers: list, data: list, header_color="#007BFF") -> BytesIO:
#     """
#     Generates a PDF report as a BytesIO stream.

#     Args:
#         title (str): Report title (not displayed in table, can be used for filename or page title)
#         headers (list): List of column headers
#         data (list): List of rows (each row is a list of column values)
#         header_color (str): Hex color for the header row

#     Returns:
#         BytesIO: PDF stream ready for StreamingResponse
#     """
#     pdf_stream = BytesIO()
#     pdf = SimpleDocTemplate(pdf_stream, pagesize=A4)
    
#     # Combine headers + data
#     table_data = [headers] + data
    
#     # Create table
#     table = Table(table_data)
    
#     # Style table
#     style = TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(header_color)),  # Header background
#         ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),                    # Header text color
#         ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
#         ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#     ])
#     table.setStyle(style)
    
#     # Build PDF
#     pdf.build([table])
#     pdf_stream.seek(0)
#     return pdf_stream

from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch

def generate_pdf_report(title, headers, data, header_color="#1f6fff"):
    pdf_stream = BytesIO()

    pdf = SimpleDocTemplate(
        pdf_stream,
        pagesize=landscape(A4),
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20,   
        title="Aircraft Report",
        author="Laminar",
    )

    table_data = [headers] + data

    # Column widths (adjusted for readability)
    col_widths = [
        1.2 * inch,  # AC REG
        1.6 * inch,  # AIRCRAFT TYPE
        1.6 * inch,  # MODEL
        1.6 * inch,  # MSN
        2.8 * inch,  # BASE LOCATION (long text)
        1.2 * inch,  # STATUS
        1.2 * inch,  # CREATED AT
    ]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(header_color)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

        # Body
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),

        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    pdf.build([table])
    pdf_stream.seek(0)
    return pdf_stream
