import decimal
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date
from decimal import Decimal
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.conf import settings
from .models import Venta, DetalleVenta, Cliente, BalanceCliente
from productos.models import Presentacion, ListaPreciosVentas
from django.core.exceptions import ValidationError
from importacion.models import Bodega, Pedido

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm, inch, cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Frame, PageTemplate
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
    from reportlab.platypus.frames import Frame
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

@login_required
def generar_factura_reportlab(request, venta_id):
    """View to generate invoice PDF using ReportLab"""
    if not REPORTLAB_AVAILABLE:
        messages.error(request, "ReportLab no está disponible. Por favor, instale la librería.")
        return redirect('comercial:generar_factura', venta_id=venta_id)

    venta = get_object_or_404(Venta, pk=venta_id)
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')

    # Create PDF response
    response = HttpResponse(content_type='application/pdf')
    filename = f"factura_{venta.numero_factura if venta.numero_factura else venta.id}_{venta.cliente.nombre.replace(' ', '_')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Create the PDF with compact margins like the HTML version
    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=0.5*cm, bottomMargin=0.5*cm, leftMargin=0.8*cm, rightMargin=0.8*cm)
    
    # Get the story (content) for the PDF
    story = []
    
    # Register fonts
    try:
        # Try to register custom fonts if they exist
        font_path = os.path.join(settings.BASE_DIR, 'comercial/static/fonts/')
        if os.path.exists(font_path):
            for font_file in os.listdir(font_path):
                if font_file.endswith('.ttf'):
                    pdfmetrics.registerFont(TTFont('CustomFont', os.path.join(font_path, font_file)))
                    font_name = 'CustomFont'
                    break
        else:
            font_name = 'Helvetica'
    except:
        font_name = 'Helvetica'
    
    # Define colors matching CSS
    primary_color = colors.HexColor('#1A7B6B')
    secondary_color = colors.HexColor('#2A9D8F')
    accent_color = colors.HexColor('#8CE2D6')
    text_color = colors.HexColor('#2c3e50')
    text_light = colors.HexColor('#7f8c8d')
    light_bg = colors.HexColor('#f8f9fa')
    logo_color = colors.HexColor('#ea1f78')
    orange_color = colors.HexColor('#ff9800')
    orange_dark = colors.HexColor('#e65100')
    orange_light = colors.HexColor('#fff3e0')
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=2,
        spaceBefore=0,
        textColor=primary_color,
        alignment=TA_CENTER,
        fontName=font_name + '-Bold' if font_name == 'Helvetica' else font_name
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=2,
        spaceBefore=0,
        textColor=primary_color,
        fontName=font_name + '-Bold' if font_name == 'Helvetica' else font_name
    )
    
    company_style = ParagraphStyle(
        'CompanyStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=text_light,
        fontName=font_name,
        leading=11
    )
    
    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=primary_color,
        fontName=font_name,
        fontWeight='bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=9,
        textColor=text_color,
        fontName=font_name,
        leading=10
    )
    
    small_style = ParagraphStyle(
        'SmallStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=text_light,
        fontName=font_name,
        leading=9
    )
    
    # Header with logo and company info
    logo_path = os.path.join(settings.BASE_DIR, 'comercial/static/img/logo-oficial.jpg')
    
    # Create logo
    if os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=2.6*cm, height=2.6*cm)
        except:
            logo = Paragraph('<font size="8">[LOGO]</font>', normal_style)
    else:
        logo = Paragraph('<font size="8">[LOGO]</font>', normal_style)
    
    # Company info
    company_info = Paragraph('''
    <b><font size="14" color="#1A7B6B">LUZ MERY MELO MEJIA</font></b><br/>
    <font size="9" color="#7f8c8d">Calle Juan de la cierva # 23</font><br/>
    <font size="9" color="#7f8c8d">08210 Barbera del valles, España</font><br/>
    <font size="9" color="#7f8c8d">Tel: +34 633 49 42 28</font><br/>
    <font size="9" color="#7f8c8d">Email: import@luzmeloexoticfruits.com</font><br/>
    <font size="9" color="#7f8c8d">CIF: 26062884C</font>
    ''', company_style)
    
    # Invoice info section
    invoice_number = f"Nº: {venta.numero_factura if venta.numero_factura else venta.id}"
    invoice_info_html = f'''
    <para alignment="right">
    <b><font size="16" color="#1A7B6B">FACTURA</font></b><br/>
    <b><font size="13" color="#2c3e50">{invoice_number}</font></b><br/><br/>
    <font size="9" color="#7f8c8d"><b>Fecha Emisión:</b> {venta.fecha_entrega.strftime("%d/%m/%Y")}</font><br/>
    <font size="9" color="#e74c3c"><b>Fecha Vencimiento:</b> {venta.fecha_vencimiento.strftime("%d/%m/%Y") if venta.fecha_vencimiento else "-"}</font><br/>
    <font size="9" color="#7f8c8d"><b>Semana:</b> {venta.semana or "-"}</font>'''
    
    if venta.origen:
        invoice_info_html += f'<br/><font size="9" color="#7f8c8d"><b>Origen:</b> {venta.origen}</font>'
    
    invoice_info_html += '</para>'
    
    invoice_info_style = ParagraphStyle(
        'InvoiceInfo',
        parent=styles['Normal'],
        fontSize=9,
        textColor=text_light,
        fontName=font_name,
        leading=11,
        alignment=TA_RIGHT
    )
    
    invoice_info = Paragraph(invoice_info_html, invoice_info_style)
    
    # Header table with logo, company info and invoice info
    header_table = Table([
        [logo, company_info, invoice_info]
    ], colWidths=[2.8*cm, 7.5*cm, 7.5*cm])
    
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('BACKGROUND', (2, 0), (2, 0), light_bg),
        ('LINEBELOW', (0, 0), (-1, -1), 2, primary_color),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 6))
    
    # Client info - Grid layout like HTML with proper spacing
    client_header = Paragraph('<b><font size="11" color="#1A7B6B">DATOS DEL CLIENTE</font></b>', header_style)
    
    pais = venta.cliente.pais if hasattr(venta.cliente, 'pais') and venta.cliente.pais else ""
    ciudad_pais = f'{venta.cliente.ciudad or "-"}, {pais}' if pais else f'{venta.cliente.ciudad or "-"}'
    
    client_data = [
        [client_header, '', ''],
        [
            Paragraph(f'<font size="9"><b color="#1A7B6B">Cliente:</b> {venta.cliente.nombre}</font>', normal_style),
            '',
            Paragraph(f'<font size="9"><b color="#1A7B6B">NIF/CIF:</b> {venta.cliente.cif or "-"}</font>', normal_style)
        ],
        [
            Paragraph(f'<font size="9"><b color="#1A7B6B">Dirección:</b> {venta.cliente.domicilio or "-"}</font>', normal_style),
            '',
            Paragraph(f'<font size="9"><b color="#1A7B6B">Ciudad:</b> {ciudad_pais}</font>', normal_style)
        ],
        [
            Paragraph(f'<font size="9"><b color="#1A7B6B">Teléfono:</b> {venta.cliente.telefono or "-"}</font>', normal_style),
            '',
            Paragraph(f'<font size="9"><b color="#1A7B6B">Email:</b> {venta.cliente.email or "-"}</font>', normal_style)
        ]
    ]
    
    client_table = Table(client_data, colWidths=[8.5*cm, 0.5*cm, 8.5*cm])
    client_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (2, 0)),
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, 0), 1, primary_color),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
    ]))
    
    story.append(client_table)
    story.append(Spacer(1, 6))
    
    # Items table
    items_header = Paragraph('<b><font size="11" color="#1A7B6B">DETALLE DE PRODUCTOS</font></b>', header_style)
    story.append(items_header)
    story.append(Spacer(1, 3))
    
    # Table headers with better alignment
    header_style_center = ParagraphStyle(
        'HeaderCenter',
        parent=normal_style,
        alignment=TA_CENTER,
        fontSize=9,
        textColor=colors.white
    )
    
    headers = [
        Paragraph('<b>Producto</b>', normal_style),
        Paragraph('<b>Presentación</b>', header_style_center),
        Paragraph('<b>Total Kg</b>', header_style_center),
        Paragraph('<b>Cajas</b>', header_style_center),
        Paragraph('<b>Precio/Caja (€)</b>', header_style_center),
        Paragraph('<b>Total (€)</b>', header_style_center)
    ]
    items_data = [headers]
    
    # Table rows with better formatting
    cell_style_center = ParagraphStyle(
        'CellCenter',
        parent=normal_style,
        alignment=TA_CENTER,
        fontSize=9
    )
    
    for detalle in detalles:
        row = [
            Paragraph(f'<font size="9">{detalle.presentacion.fruta.nombre}</font>', normal_style),
            Paragraph(f'<font size="9">{detalle.presentacion.kilos} kg</font>', cell_style_center),
            Paragraph(f'<font size="9">{detalle.kilos:.2f}</font>', cell_style_center),
            Paragraph(f'<font size="9">{detalle.cajas_enviadas}</font>', cell_style_center),
            Paragraph(f'<font size="9">{detalle.valor_x_caja_euro:.2f} €</font>', cell_style_center),
            Paragraph(f'<font size="9">{detalle.valor_x_producto:.2f} €</font>', cell_style_center)
        ]
        items_data.append(row)
    
    # Create items table with better column widths
    items_table = Table(items_data, colWidths=[4*cm, 2.5*cm, 2*cm, 1.8*cm, 2.8*cm, 2.7*cm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, primary_color),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_bg]),
    ]))
    
    story.append(items_table)
    story.append(Spacer(1, 6))
    
    # Bank info and summary section with better spacing
    # Bank information
    bank_title = Paragraph('<b><font size="9" color="#1A7B6B">DATOS BANCARIOS</font></b>', small_style)
    bank_content = Paragraph('<font size="8" color="#7f8c8d"><b>Banco:</b> Banco Santander<br/><b>IBAN:</b> ES76 0049 0030 2821 1019 2726<br/><b>SWIFT/BIC:</b> XXX-XXX-XXX</font>', small_style)
    
    bank_table = Table([[bank_title], [bank_content]], colWidths=[8*cm])
    bank_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, 0), 1, primary_color),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
    ]))
    
    # Terms
    terms_title = Paragraph('<b><font size="9" color="#1A7B6B">TÉRMINOS Y CONDICIONES DE PAGO</font></b>', small_style)
    terms_content = Paragraph(f'<font size="8" color="#7f8c8d">Pago a {venta.cliente.dias_pago} días de la fecha de emisión de la factura.<br/>Forma de pago: Transferencia bancaria.</font>', small_style)
    
    terms_table = Table([[terms_title], [terms_content]], colWidths=[8*cm])
    terms_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, 0), 1, primary_color),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
    ]))
    
    bank_terms_col = Table([[bank_table], [Spacer(1, 3)], [terms_table]], colWidths=[8*cm])
    bank_terms_col.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    # Summary with orange highlight for Total Cajas and better alignment
    summary_style_right = ParagraphStyle(
        'SummaryRight',
        parent=normal_style,
        alignment=TA_RIGHT,
        fontSize=9
    )
    
    summary_data = [
        [Paragraph('<b><font size="10" color="#e65100">Total Cajas:</font></b>', summary_style_right),
         Paragraph(f'<b><font size="10" color="#e65100">{venta.total_cajas_pedido}</font></b>', summary_style_right)],
        [Paragraph('<font size="9">Base Imponible:</font>', summary_style_right),
         Paragraph(f'<font size="9">{venta.subtotal_factura:.2f} €</font>', summary_style_right)],
        [Paragraph('<font size="9">IVA (4%):</font>', summary_style_right),
         Paragraph(f'<font size="9">{venta.iva:.2f} €</font>', summary_style_right)],
        [Paragraph('<b><font size="11" color="white">TOTAL FACTURA:</font></b>', summary_style_right),
         Paragraph(f'<b><font size="11" color="white">{venta.valor_total_factura_euro:.2f} €</font></b>', summary_style_right)]
    ]
    
    summary_table = Table(summary_data, colWidths=[5.5*cm, 4*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), orange_light),
        ('TEXTCOLOR', (0, 0), (-1, 0), orange_dark),
        ('BACKGROUND', (0, 1), (-1, 2), light_bg),
        ('BACKGROUND', (0, 3), (-1, 3), logo_color),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
        ('LINEABOVE', (0, 3), (-1, 3), 2, text_color),
        ('LINEBEFORE', (0, 0), (0, 0), 3, orange_color),
    ]))
    
    # Combine bank info and summary
    bottom_table = Table([[bank_terms_col, summary_table]], colWidths=[8*cm, 9.5*cm])
    bottom_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    story.append(bottom_table)
    story.append(Spacer(1, 6))
    
    # Notes with better spacing
    notes_title = Paragraph('<b><font size="10" color="#2c3e50">OBSERVACIONES</font></b>', header_style)
    notes_content = Paragraph(f'<font size="9" color="#666666">{venta.observaciones if venta.observaciones else "Sin observaciones."}</font>', small_style)
    
    notes_table = Table([[notes_title], [notes_content]], colWidths=[17.8*cm])
    notes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#ddd')),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
    ]))
    
    story.append(notes_table)
    story.append(Spacer(1, 6))
    
    # Thank you message with better styling
    thank_you_style = ParagraphStyle(
        'ThankYou',
        parent=title_style,
        fontSize=11,
        textColor=logo_color,
        alignment=TA_CENTER
    )
    
    thank_you_table = Table([[Paragraph('<b>¡Gracias por su confianza!</b>', thank_you_style)]], colWidths=[17.8*cm])
    thank_you_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
    ]))
    story.append(thank_you_table)
    
    # Build PDF
    doc.build(story)
    
    return response