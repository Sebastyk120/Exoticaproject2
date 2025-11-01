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
    
    # Create the PDF
    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm, leftMargin=1*cm, rightMargin=1*cm)
    
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
    
    # Define colors
    primary_color = colors.Color(26/255, 123/255, 107/255)  # #1A7B6B
    secondary_color = colors.Color(42/255, 157/255, 143/255)  # #2A9D8F
    accent_color = colors.Color(140/255, 226/255, 214/255)  # #8CE2D6
    text_color = colors.Color(44/255, 62/255, 80/255)  # #2c3e50
    light_bg = colors.Color(248/255, 249/255, 250/255)  # #f8f9fa
    logo_color = colors.Color(234/255, 31/255, 120/255)  # #ea1f78
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=6,
        textColor=primary_color,
        alignment=TA_CENTER,
        fontName=font_name,
        fontWeight='bold'
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=6,
        spaceBefore=12,
        textColor=primary_color,
        fontName=font_name,
        fontWeight='bold'
    )
    
    company_style = ParagraphStyle(
        'CompanyStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=text_color,
        fontName=font_name,
        leading=14
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
        fontSize=10,
        textColor=text_color,
        fontName=font_name,
        leading=12
    )
    
    # Header with logo and company info
    header_data = []
    
    # Logo section
    logo_path = os.path.join(settings.BASE_DIR, 'comercial/static/img/logo-oficial.jpg')
    if os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=2*cm, height=2*cm)
            header_data.append([logo, ''])
        except:
            # Fallback if image can't be loaded
            header_data.append(['[LOGO]', ''])
    else:
        header_data.append(['[LOGO]', ''])
    
    # Company info
    company_info = f"""
    <b style="color:{primary_color}; font-size:18px;">LUZ MERY MELO MEJIA</b><br/>
    <font size="10">Calle Juan de la cierva # 23</font><br/>
    <font size="10">08210 Barbera del valles, España</font><br/>
    <font size="10">Tel: +34 633 49 42 28</font><br/>
    <font size="10">Email: import@luzmeloexoticfruits.com</font><br/>
    <font size="10">CIF: 26062884C</font>
    """
    header_data[0][1] = Paragraph(company_info, company_style)
    
    # Invoice info
    invoice_title = Paragraph('<b style="font-size:20px; color:' + str(primary_color) + ';">FACTURA</b>', title_style)
    invoice_number = f"Nº: {venta.numero_factura if venta.numero_factura else venta.id}"
    invoice_date = f"<b>Fecha Emisión:</b> {venta.fecha_entrega.strftime('%d/%m/%Y')}"
    invoice_due = f"<b>Fecha Vencimiento:</b> {venta.fecha_vencimiento.strftime('%d/%m/%Y') if venta.fecha_vencimiento else '-'}"
    invoice_week = f"<b>Semana:</b> {venta.semana or '-'}"
    invoice_origin = f"<b>Origen:</b> {venta.origen}" if venta.origen else ""
    
    invoice_info = f"""
    <b style="font-size:16px; color:{logo_color};">{invoice_number}</b><br/><br/>
    {invoice_date}<br/>
    <font color="red"><b>Fecha Vencimiento:</b> {venta.fecha_vencimiento.strftime('%d/%m/%Y') if venta.fecha_vencimiento else '-'}</font><br/>
    {invoice_week}<br/>
    {invoice_origin}
    """
    
    header_data.append([invoice_title, Paragraph(invoice_info, normal_style)])
    
    header_table = Table(header_data, colWidths=[8*cm, 8*cm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
        ('BACKGROUND', (0, 1), (1, 1), light_bg),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 12))
    
    # Client info
    client_data = [
        [Paragraph('<b style="color:' + str(primary_color) + ';">DATOS DEL CLIENTE</b>', header_style)],
        [
            Paragraph(f'<b>Cliente:</b> {venta.cliente.nombre}', normal_style),
            Paragraph(f'<b>NIF/CIF:</b> {venta.cliente.cif or "-"}', normal_style),
            Paragraph(f'<b>Dirección:</b> {venta.cliente.domicilio or "-"}', normal_style),
            Paragraph(f'<b>Ciudad:</b> {venta.cliente.ciudad or "-"}, {venta.cliente.pais or "-"}', normal_style),
            Paragraph(f'<b>Teléfono:</b> {venta.cliente.telefono or "-"}', normal_style),
            Paragraph(f'<b>Email:</b> {venta.cliente.email or "-"}', normal_style)
        ]
    ]
    
    client_table = Table(client_data, colWidths=[16*cm])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), light_bg),
        ('TEXTCOLOR', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), light_bg),
        ('GRID', (0, 0), (-1, -1), 1, primary_color),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(client_table)
    story.append(Spacer(1, 12))
    
    # Items table
    items_data = [
        [Paragraph('<b>DETALLE DE PRODUCTOS</b>', header_style)]
    ]
    
    # Table headers
    headers = ['Producto', 'Presentación', 'Total Kg', 'Cajas', 'Precio/Caja (€)', 'Total (€)']
    items_data.append(headers)
    
    # Table rows
    for detalle in detalles:
        row = [
            Paragraph(detalle.presentacion.fruta.nombre, normal_style),
            Paragraph(f"{detalle.presentacion.kilos} kg", normal_style),
            Paragraph(f"{detalle.kilos:.2f}", normal_style),
            Paragraph(f"{detalle.cajas_enviadas}", normal_style),
            Paragraph(f"{detalle.valor_x_caja_euro:.2f} €", normal_style),
            Paragraph(f"{detalle.valor_x_producto:.2f} €", normal_style)
        ]
        items_data.append(row)
    
    # Create items table
    items_table = Table(items_data, colWidths=[3.5*cm, 2*cm, 2*cm, 2*cm, 3*cm, 3.5*cm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Product name left aligned
        ('FONTNAME', (0, 0), (-1, 0), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, primary_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_bg]),
    ]))
    
    story.append(items_table)
    story.append(Spacer(1, 12))
    
    # Bank info and summary
    bank_terms_data = []
    
    # Bank information
    bank_info = f"""
    <b style="color:{primary_color};">DATOS BANCARIOS</b><br/>
    <b>Banco:</b> Banco Santander<br/>
    <b>IBAN:</b> ES76 0049 0030 2821 1019 2726<br/>
    <b>SWIFT/BIC:</b> XXX-XXX-XXX
    """
    bank_terms_data.append([Paragraph(bank_info, normal_style)])
    
    # Terms
    terms_info = f"""
    <b style="color:{primary_color};">TÉRMINOS Y CONDICIONES DE PAGO</b><br/>
    Pago a {venta.cliente.dias_pago} días de la fecha de emisión de la factura.<br/>
    Forma de pago: Transferencia bancaria.
    """
    bank_terms_data.append([Paragraph(terms_info, normal_style)])
    
    # Summary
    summary_data = [
        ['Total Cajas:', f"{venta.total_cajas_pedido}"],
        ['Base Imponible:', f"{venta.subtotal_factura:.2f} €"],
        ['IVA (4%):', f"{venta.iva:.2f} €"],
        ['TOTAL FACTURA:', f"{venta.valor_total_factura_euro:.2f} €"]
    ]
    
    summary_table = Table(summary_data, colWidths=[6*cm, 4*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -2), light_bg),
        ('BACKGROUND', (0, -1), (-1, -1), logo_color),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -2), font_name),
        ('FONTNAME', (0, -1), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -2), 10),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('FONTWEIGHT', (0, -1), (-1, -1), 'bold'),
        ('GRID', (0, 0), (-1, -1), 1, primary_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    # Combine bank info and summary
    bottom_data = [
        [Table(bank_terms_data, colWidths=[8*cm]), summary_table]
    ]
    
    bottom_table = Table(bottom_data, colWidths=[8*cm, 10*cm])
    bottom_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    story.append(bottom_table)
    story.append(Spacer(1, 12))
    
    # Notes
    notes_data = [
        [Paragraph('<b style="color:' + str(primary_color) + ';">OBSERVACIONES</b>', header_style)],
        [Paragraph(venta.observaciones if venta.observaciones else 'Sin observaciones.', normal_style)]
    ]
    
    notes_table = Table(notes_data, colWidths=[16*cm])
    notes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), light_bg),
        ('TEXTCOLOR', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), light_bg),
        ('GRID', (0, 0), (-1, -1), 1, primary_color),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(notes_table)
    story.append(Spacer(1, 12))
    
    # Thank you message
    thank_you = Paragraph(f'<b style="color:{logo_color}; font-size:14px; text-align:center;">¡Gracias por su confianza!</b>', title_style)
    story.append(thank_you)
    
    # Build PDF
    doc.build(story)
    
    return response