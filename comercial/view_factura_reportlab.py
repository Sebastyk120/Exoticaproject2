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
    header_data = []
    
    # Logo section
    logo_path = os.path.join(settings.BASE_DIR, 'comercial/static/img/logo-oficial.jpg')
    
    # Company info with logo
    company_col = []
    if os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=2.6*cm, height=2.6*cm)
            company_col.append([logo])
        except:
            company_col.append([Paragraph('[LOGO]', normal_style)])
    else:
        company_col.append([Paragraph('[LOGO]', normal_style)])
    
    # Company title and details
    company_title = ParagraphStyle(
        'CompanyTitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=primary_color,
        fontName=font_name + '-Bold' if font_name == 'Helvetica' else font_name,
        leading=16
    )
    
    company_info = f"""
    <b><font size="14" color="#1A7B6B">LUZ MERY MELO MEJIA</font></b><br/>
    <font size="9" color="#7f8c8d">Calle Juan de la cierva # 23</font><br/>
    <font size="9" color="#7f8c8d">08210 Barbera del valles, España</font><br/>
    <font size="9" color="#7f8c8d">Tel: +34 633 49 42 28</font><br/>
    <font size="9" color="#7f8c8d">Email: import@luzmeloexoticfruits.com</font><br/>
    <font size="9" color="#7f8c8d">CIF: 26062884C</font>
    """
    
    company_table = Table([[logo if os.path.exists(logo_path) else Paragraph('[LOGO]', normal_style), Paragraph(company_info, company_style)]],
                         colWidths=[2.6*cm, 6*cm])
    company_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    
    # Invoice info
    invoice_title = Paragraph('<b><font size="16" color="#1A7B6B">FACTURA</font></b>', title_style)
    invoice_number = f"Nº: {venta.numero_factura if venta.numero_factura else venta.id}"
    
    invoice_info_parts = [
        invoice_title,
        Paragraph(f'<b><font size="13" color="#2c3e50">{invoice_number}</font></b>', normal_style),
        Spacer(1, 2),
        Paragraph(f'<font size="9" color="#7f8c8d"><b>Fecha Emisión:</b> {venta.fecha_entrega.strftime("%d/%m/%Y")}</font>', small_style),
        Paragraph(f'<font size="9" color="#e74c3c"><b>Fecha Vencimiento:</b> {venta.fecha_vencimiento.strftime("%d/%m/%Y") if venta.fecha_vencimiento else "-"}</font>', small_style),
        Paragraph(f'<font size="9" color="#7f8c8d"><b>Semana:</b> {venta.semana or "-"}</font>', small_style),
    ]
    
    if venta.origen:
        invoice_info_parts.append(Paragraph(f'<font size="9" color="#7f8c8d"><b>Origen:</b> {venta.origen}</font>', small_style))
    
    invoice_table = Table([[p] for p in invoice_info_parts], colWidths=[5*cm])
    invoice_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
    ]))
    
    header_table = Table([[company_table, invoice_table]], colWidths=[9*cm, 9*cm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 2, primary_color),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 4))
    
    # Client info - Grid layout like HTML
    client_header = Paragraph('<b><font size="11" color="#1A7B6B">DATOS DEL CLIENTE</font></b>', header_style)
    
    pais = venta.cliente.pais if hasattr(venta.cliente, 'pais') and venta.cliente.pais else ""
    ciudad_pais = f'{venta.cliente.ciudad or "-"}, {pais}' if pais else f'{venta.cliente.ciudad or "-"}'
    
    client_data = [
        [client_header, ''],
        [
            Paragraph(f'<font size="9"><b color="#1A7B6B">Cliente:</b> {venta.cliente.nombre}</font>', normal_style),
            Paragraph(f'<font size="9"><b color="#1A7B6B">NIF/CIF:</b> {venta.cliente.cif or "-"}</font>', normal_style)
        ],
        [
            Paragraph(f'<font size="9"><b color="#1A7B6B">Dirección:</b> {venta.cliente.domicilio or "-"}</font>', normal_style),
            Paragraph(f'<font size="9"><b color="#1A7B6B">Ciudad:</b> {ciudad_pais}</font>', normal_style)
        ],
        [
            Paragraph(f'<font size="9"><b color="#1A7B6B">Teléfono:</b> {venta.cliente.telefono or "-"}</font>', normal_style),
            Paragraph(f'<font size="9"><b color="#1A7B6B">Email:</b> {venta.cliente.email or "-"}</font>', normal_style)
        ]
    ]
    
    client_table = Table(client_data, colWidths=[9*cm, 9*cm])
    client_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, 0), 1, primary_color),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
    ]))
    
    story.append(client_table)
    story.append(Spacer(1, 4))
    
    # Items table
    items_header = Paragraph('<b><font size="11" color="#1A7B6B">DETALLE DE PRODUCTOS</font></b>', header_style)
    story.append(items_header)
    story.append(Spacer(1, 2))
    
    # Table headers
    headers = [
        Paragraph('<b><font size="9" color="white">Producto</font></b>', normal_style),
        Paragraph('<b><font size="9" color="white">Presentación</font></b>', normal_style),
        Paragraph('<b><font size="9" color="white">Total Kg</font></b>', normal_style),
        Paragraph('<b><font size="9" color="white">Cajas</font></b>', normal_style),
        Paragraph('<b><font size="9" color="white">Precio/Caja (€)</font></b>', normal_style),
        Paragraph('<b><font size="9" color="white">Total (€)</font></b>', normal_style)
    ]
    items_data = [headers]
    
    # Table rows
    for detalle in detalles:
        row = [
            Paragraph(f'<font size="9">{detalle.presentacion.fruta.nombre}</font>', normal_style),
            Paragraph(f'<font size="9">{detalle.presentacion.kilos} kg</font>', normal_style),
            Paragraph(f'<font size="9">{detalle.kilos:.2f}</font>', normal_style),
            Paragraph(f'<font size="9">{detalle.cajas_enviadas}</font>', normal_style),
            Paragraph(f'<font size="9">{detalle.valor_x_caja_euro:.2f} €</font>', normal_style),
            Paragraph(f'<font size="9">{detalle.valor_x_producto:.2f} €</font>', normal_style)
        ]
        items_data.append(row)
    
    # Create items table
    items_table = Table(items_data, colWidths=[3.5*cm, 2.5*cm, 2*cm, 1.8*cm, 3*cm, 3*cm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Product name left aligned
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Other columns center aligned
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('GRID', (0, 0), (-1, -1), 0.5, primary_color),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_bg]),
    ]))
    
    story.append(items_table)
    story.append(Spacer(1, 4))
    
    # Bank info and summary section
    # Bank information
    bank_title = Paragraph('<b><font size="8" color="#1A7B6B">DATOS BANCARIOS</font></b>', small_style)
    bank_content = Paragraph('<font size="7" color="#7f8c8d"><b>Banco:</b> Banco Santander<br/><b>IBAN:</b> ES76 0049 0030 2821 1019 2726<br/><b>SWIFT/BIC:</b> XXX-XXX-XXX</font>', small_style)
    
    bank_table = Table([[bank_title], [bank_content]], colWidths=[8*cm])
    bank_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, 0), 1, primary_color),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
    ]))
    
    # Terms
    terms_title = Paragraph('<b><font size="8" color="#1A7B6B">TÉRMINOS Y CONDICIONES DE PAGO</font></b>', small_style)
    terms_content = Paragraph(f'<font size="7" color="#7f8c8d">Pago a {venta.cliente.dias_pago} días de la fecha de emisión de la factura.<br/>Forma de pago: Transferencia bancaria.</font>', small_style)
    
    terms_table = Table([[terms_title], [terms_content]], colWidths=[8*cm])
    terms_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, 0), 1, primary_color),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
    ]))
    
    bank_terms_col = Table([[bank_table], [Spacer(1, 2)], [terms_table]], colWidths=[8*cm])
    bank_terms_col.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    # Summary with orange highlight for Total Cajas
    summary_data = [
        [Paragraph('<font size="9">Total Cajas:</font>', normal_style),
         Paragraph(f'<font size="9">{venta.total_cajas_pedido}</font>', normal_style)],
        [Paragraph('<font size="9">Base Imponible:</font>', normal_style),
         Paragraph(f'<font size="9">{venta.subtotal_factura:.2f} €</font>', normal_style)],
        [Paragraph('<font size="9">IVA (4%):</font>', normal_style),
         Paragraph(f'<font size="9">{venta.iva:.2f} €</font>', normal_style)],
        [Paragraph('<b><font size="11" color="white">TOTAL FACTURA:</font></b>', normal_style),
         Paragraph(f'<b><font size="11" color="white">{venta.valor_total_factura_euro:.2f} €</font></b>', normal_style)]
    ]
    
    summary_table = Table(summary_data, colWidths=[5*cm, 4.5*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), orange_light),  # Orange background for Total Cajas
        ('TEXTCOLOR', (0, 0), (-1, 0), orange_dark),
        ('BACKGROUND', (0, 1), (-1, 2), light_bg),
        ('BACKGROUND', (0, 3), (-1, 3), logo_color),  # Pink background for total
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
        ('LINEABOVE', (0, 3), (-1, 3), 2, text_color),
        ('LINEBEFORE', (0, 0), (0, 0), 3, orange_color),  # Orange left border for Total Cajas
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
    story.append(Spacer(1, 4))
    
    # Notes
    notes_title = Paragraph('<b><font size="10" color="#2c3e50">OBSERVACIONES</font></b>', header_style)
    notes_content = Paragraph(f'<font size="8" color="#666666">{venta.observaciones if venta.observaciones else "Sin observaciones."}</font>', small_style)
    
    notes_table = Table([[notes_title], [notes_content]], colWidths=[18*cm])
    notes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#ddd')),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
    ]))
    
    story.append(notes_table)
    story.append(Spacer(1, 4))
    
    # Thank you message
    thank_you_table = Table([[Paragraph('<b><font size="11" color="#ea1f78">¡Gracias por su confianza!</font></b>', title_style)]], colWidths=[18*cm])
    thank_you_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
    ]))
    story.append(thank_you_table)
    
    # Build PDF
    doc.build(story)
    
    return response