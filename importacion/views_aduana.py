import re
import logging
from decimal import Decimal
import io

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django import forms
from django.core.files.base import ContentFile
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

import pdfplumber

from .models import GastosAduana, AgenciaAduana, Pedido

# Setup logging
logger = logging.getLogger(__name__)


class PDFUploadForm(forms.Form):
    pdf_file = forms.FileField(label='Selecciona un archivo PDF')


def parse_amount(amount_str):
    """Converts a Spanish formatted number string (1.234,56) to Decimal."""
    if not amount_str:
        return Decimal('0.00')
    # Remove thousands separator (.) and replace decimal separator (,) with .
    clean_str = amount_str.replace('.', '').replace(',', '.')
    try:
        return Decimal(clean_str)
    except:
        return Decimal('0.00')


def format_awb(awb_raw):
    """Formats AWB as XXX-XXXXXXXX"""
    if len(awb_raw) == 11:
        return f"{awb_raw[:3]}-{awb_raw[3:]}"
    return awb_raw


def extract_invoice_data_with_pdfplumber(pdf_content):
    """
    Extrae datos de la factura de aduana usando pdfplumber
    """
    try:
        data = {
            "agencia_aduana": "No encontrado",
            "numero_factura": "No encontrado",
            "awbs": [],
            "valor_gastos_aduana": Decimal('0.00'),
            "iva_importacion": Decimal('0.00'),
            "iva_sobre_base": Decimal('0.00')
        }

        # Abrir el PDF desde el contenido en memoria
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            full_text = ""
            for page in pdf.pages:
                # layout=True preserves the visual structure, useful for tables
                full_text += page.extract_text(layout=True) + "\n"

            logger.info(f"[ADUANA] Texto extraído (primeros 500 caracteres): {full_text[:500]}...")

            # 1. Agencia de Aduana
            if "Arola Aduanas y Consignaciones" in full_text:
                data["agencia_aduana"] = "Arola Aduanas y Consignaciones, S.L."

            # 2. Número de Factura
            # Pattern: 25-FV-XXXXXX
            inv_match = re.search(r'(\d{2}-FV-\d{6})', full_text)
            if inv_match:
                data["numero_factura"] = inv_match.group(1)

            # 3. AWBs
            # Pattern: 729 followed by 8 digits (11 digits total)
            # We use lookarounds to ensure we match the full number
            awb_matches = re.findall(r'(?<!\d)(729\d{8})(?!\d)', full_text)
            unique_awbs = sorted(list(set(awb_matches)))
            data["awbs"] = [format_awb(awb) for awb in unique_awbs]

            # 4. IVA Importación
            # Pattern: 54IVA (Importación) ... value
            # We find all occurrences and sum them up to get the total expense.
            iva_imp_matches = re.findall(r'54IVA\s*\(Importaci[óo]n\).*?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text, re.IGNORECASE)

            total_iva_imp = Decimal('0.00')
            for val in iva_imp_matches:
                total_iva_imp += parse_amount(val)
            data["iva_importacion"] = total_iva_imp

            # 5. Total Gastos Aduana (Total Factura)
            # Format 2 explicit: Total Factura (EUR) 1.289,94
            total_match_f2 = re.search(r'Total\s+Factura\s*\(EUR\)\s*(\d{1,3}(?:\.\d{3})*,\d{2})', full_text, re.IGNORECASE)

            if total_match_f2:
                data["valor_gastos_aduana"] = parse_amount(total_match_f2.group(1))
            else:
                # Format 1: Look for the line starting with EUR (Currency) in the summary
                # EUR 1.041,13 403,24 637,89 21 133,96 1.175,09
                eur_line_match = re.search(r'EUR\s+.*?\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s*$', full_text, re.MULTILINE)
                if eur_line_match:
                    data["valor_gastos_aduana"] = parse_amount(eur_line_match.group(1))

            # 6. IVA Sobre Base
            # Format 2: IVA 21% sobre Base 151,86
            iva_base_match_f2 = re.search(r'IVA\s+21%\s+sobre\s+Base\s+(\d{1,3}(?:\.\d{3})*,\d{2})', full_text, re.IGNORECASE)
            if iva_base_match_f2:
                data["iva_sobre_base"] = parse_amount(iva_base_match_f2.group(1))
            else:
                # Format 1: Look for summary table row starting with IVA21
                # IVA21 637,89 21 133,96 771,85
                # We want the 3rd number (133,96)
                iva_row_match = re.search(r'IVA21\s+[\d.,]+\s+21\s+(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
                if iva_row_match:
                    data["iva_sobre_base"] = parse_amount(iva_row_match.group(1))

        return data

    except Exception as e:
        logger.error(f"[ADUANA] Error al procesar documento con pdfplumber: {str(e)}")
        raise


@login_required
def process_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = form.cleaned_data['pdf_file']
            pdf_file.seek(0)  # Reiniciar puntero

            # Leer el contenido del PDF
            pdf_content = pdf_file.read()

            try:
                # Extraer datos usando pdfplumber
                data = extract_invoice_data_with_pdfplumber(pdf_content)

                # Extraer valores del diccionario
                agencia_aduana_name = data["agencia_aduana"]
                numero_factura = data["numero_factura"]
                pedidos_matches = data["awbs"]
                valor_gastos_aduana = data["valor_gastos_aduana"]
                iva_importacion = data["iva_importacion"]
                iva_sobre_base = data["iva_sobre_base"]

                logger.info(f"[ADUANA] Agencia: {agencia_aduana_name}")
                logger.info(f"[ADUANA] Número de factura: {numero_factura}")
                logger.info(f"[ADUANA] AWBs encontrados: {pedidos_matches}")
                logger.info(f"[ADUANA] Valor gastos aduana: {valor_gastos_aduana}")
                logger.info(f"[ADUANA] IVA Importación: {iva_importacion}")
                logger.info(f"[ADUANA] IVA Sobre Base: {iva_sobre_base}")

                # Verificar si ya existe un gasto con este número de factura
                existing_gasto = GastosAduana.objects.filter(numero_factura=numero_factura).first()
                if existing_gasto:
                    pedidos_info = ", ".join([p.awb for p in existing_gasto.pedidos.all()[:3]])
                    if existing_gasto.pedidos.count() > 3:
                        pedidos_info += f" (y {existing_gasto.pedidos.count() - 3} más)"

                    return JsonResponse({
                        'success': False,
                        'error': f'Ya existe un gasto registrado con el número de factura {numero_factura}. '
                                f'Agencia: {existing_gasto.agencia_aduana.nombre}. '
                                f'Valor: €{existing_gasto.valor_gastos_aduana}. '
                                f'AWBs asociados: {pedidos_info if pedidos_info else "Ninguno"}.'
                    })

                # Extraer conceptos (opcional, puede ser mejorado en el futuro)
                conceptos_text = f"Factura procesada con pdfplumber - Agencia: {agencia_aduana_name}"

            except Exception as e:
                logger.error(f"[ADUANA] Error al procesar con pdfplumber: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Error al procesar el PDF con pdfplumber: {str(e)}'
                })

            # Get or create AgenciaAduana instance
            agencia, _ = AgenciaAduana.objects.get_or_create(nombre=agencia_aduana_name)

            # Get Pedido instances using the AWB field
            try:
                matching_pedidos = []

                for awb in pedidos_matches:
                    pedidos = Pedido.objects.filter(awb=awb)
                    if pedidos.exists():
                        matching_pedidos.extend(pedidos)

                if not matching_pedidos:
                    return JsonResponse({
                        'success': False,
                        'error': f'No se encontraron pedidos con los AWBs proporcionados: {pedidos_matches}'
                    })

                logger.info(f"[ADUANA] Pedidos encontrados: {len(matching_pedidos)}")

            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Error al buscar pedidos: {str(e)}'
                })

            # Crear instancia de GastosAduana
            try:
                gastos = GastosAduana(
                    agencia_aduana=agencia,
                    numero_factura=numero_factura,
                    valor_gastos_aduana=valor_gastos_aduana,
                    conceptos=conceptos_text,
                    iva_importacion=iva_importacion,
                    iva_sobre_base=iva_sobre_base
                )

                # Save the gasto first (without PDF)
                gastos.save()

                # Agregar todos los pedidos encontrados
                for pedido in matching_pedidos:
                    gastos.pedidos.add(pedido)

                # Guardar el archivo PDF (el upload_to ya usa la fecha del primer pedido)
                if pdf_file:
                    # Generar un nombre de archivo único basado en el número de factura
                    pdf_filename = f"aduana_{numero_factura.replace('/', '_')}_{pdf_file.name}"
                    # Reiniciar el puntero del archivo antes de guardarlo
                    pdf_file.seek(0)
                    gastos.pdf_file.save(pdf_filename, ContentFile(pdf_file.read()), save=True)

                return JsonResponse({
                    'success': True,
                    'message': 'PDF procesado correctamente'
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Error al guardar GastosAduana: {str(e)}'
                })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Formulario inválido'
            })
    else:
        form = PDFUploadForm()

    # --- Inicio: filtros y paginación de gastos ---
    numero_factura_query = request.GET.get('numero_factura', '').strip()
    semana_query = request.GET.get('semana', '').strip()
    gastos_list = GastosAduana.objects.all().order_by('-id')
    if numero_factura_query:
        gastos_list = gastos_list.filter(numero_factura__icontains=numero_factura_query)
    if semana_query:
        # Filter based on the week of associated pedidos
        gastos_list = gastos_list.filter(pedidos__semana=semana_query).distinct()

    paginator = Paginator(gastos_list, 20) # Show 10 gastos per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get distinct weeks from Pedido model for the filter dropdown
    semanas = Pedido.objects.values_list('semana', flat=True).distinct().order_by('semana')
    # --- Fin: filtros y paginación ---

    # Get all agencias and pedidos for the create form
    agencias = AgenciaAduana.objects.all()
    pedidos_disponibles = Pedido.objects.all()
    
    # Log the number of pedidos for debugging
    logger.info(f"Cantidad de pedidos disponibles para aduana: {pedidos_disponibles.count()}")
    
    return render(request, 'aduana/upload_pdf_aduana.html', {
        'form': form,
        'page_obj': page_obj, # Pass paginated object
        'numero_factura_query': numero_factura_query, # Pass filter value
        'semana_query': semana_query, # Pass filter value
        'semanas': semanas, # Pass available weeks
        'agencias': agencias,
        'pedidos_disponibles': pedidos_disponibles
    })


@login_required
@require_http_methods(["GET"])
def get_gasto(request, gasto_id):
    gasto = get_object_or_404(GastosAduana, id=gasto_id)
    primer_pedido = gasto.pedidos.first()
    semana = primer_pedido.semana if primer_pedido else None
    data = {
        'id': gasto.id,
        'numero_factura': gasto.numero_factura,
        'agencia_aduana': gasto.agencia_aduana.nombre,
        'agencia_aduana_id': gasto.agencia_aduana.id,
        'valor_gastos_aduana': str(gasto.valor_gastos_aduana),
        'numero_nota_credito': gasto.numero_nota_credito,
        'valor_nota_credito': str(gasto.valor_nota_credito) if gasto.valor_nota_credito else "",
        'monto_pendiente': str(gasto.monto_pendiente) if gasto.monto_pendiente else "",
        'pagado': gasto.pagado,
        'iva_importacion': str(gasto.iva_importacion) if gasto.iva_importacion else "0.00",
        'iva_sobre_base': str(gasto.iva_sobre_base) if gasto.iva_sobre_base else "0.00",
        'pedidos': [f"{pedido.id} - {str(pedido)}" for pedido in gasto.pedidos.all()],
        'pedidos_ids': [pedido.id for pedido in gasto.pedidos.all()],
        'semana': semana,
        'pdf_file': gasto.pdf_file.url if gasto.pdf_file else None,
        'pdf_file_rectificativa': gasto.pdf_file_rectificativa.url if gasto.pdf_file_rectificativa else None
    }
    return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
def update_gasto(request, gasto_id):
    gasto = get_object_or_404(GastosAduana, id=gasto_id)
    try:
        gasto.numero_factura = request.POST.get('numero_factura')
        gasto.valor_gastos_aduana = Decimal(request.POST.get('valor_gastos_aduana'))
        gasto.numero_nota_credito = request.POST.get('numero_nota_credito')

        valor_nota_credito = request.POST.get('valor_nota_credito')
        if valor_nota_credito and valor_nota_credito.strip():
            gasto.valor_nota_credito = Decimal(valor_nota_credito)
        else:
            gasto.valor_nota_credito = None

        # Add IVA fields to update process
        iva_importacion = request.POST.get('iva_importacion')
        if iva_importacion and iva_importacion.strip():
            gasto.iva_importacion = Decimal(iva_importacion)

        iva_sobre_base = request.POST.get('iva_sobre_base')
        if iva_sobre_base and iva_sobre_base.strip():
            gasto.iva_sobre_base = Decimal(iva_sobre_base)

        gasto.save()

        # Handle PDF file if provided
        pdf_file = request.FILES.get('pdf_file')
        if pdf_file:
            pdf_filename = f"aduana_edit_{gasto.numero_factura.replace('/', '_')}_{pdf_file.name}"
            gasto.pdf_file.save(pdf_filename, ContentFile(pdf_file.read()), save=True)

        # Handle PDF rectificativa file if provided
        pdf_file_rectificativa = request.FILES.get('pdf_file_rectificativa')
        if pdf_file_rectificativa:
            pdf_filename_rect = f"aduana_rect_{gasto.numero_factura.replace('/', '_')}_{pdf_file_rectificativa.name}"
            gasto.pdf_file_rectificativa.save(pdf_filename_rect, ContentFile(pdf_file_rectificativa.read()), save=True)

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_gasto(request, gasto_id):
    gasto = get_object_or_404(GastosAduana, id=gasto_id)
    try:
        gasto.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def create_gasto(request):
    try:
        # Extract form data
        agencia_id = request.POST.get('agencia_aduana')
        numero_factura = request.POST.get('numero_factura')
        valor_gastos_aduana = Decimal(request.POST.get('valor_gastos_aduana'))
        iva_importacion_str = request.POST.get('iva_importacion', '')
        iva_sobre_base_str = request.POST.get('iva_sobre_base', '')
        numero_nota_credito = request.POST.get('numero_nota_credito', '')
        valor_nota_credito_str = request.POST.get('valor_nota_credito', '')

        # Get PDF file if provided
        pdf_file = request.FILES.get('pdf_file')

        # Validate numero_factura is unique
        if GastosAduana.objects.filter(numero_factura=numero_factura).exists():
            return JsonResponse({
                'success': False,
                'error': f'Ya existe un gasto con el número de factura {numero_factura}'
            })

        # Get agencia
        agencia = get_object_or_404(AgenciaAduana, id=agencia_id)

        # Create gasto with required fields
        gasto = GastosAduana(
            agencia_aduana=agencia,
            numero_factura=numero_factura,
            valor_gastos_aduana=valor_gastos_aduana,
        )

        # Process optional fields if provided
        if iva_importacion_str and iva_importacion_str.strip():
            gasto.iva_importacion = Decimal(iva_importacion_str)

        if iva_sobre_base_str and iva_sobre_base_str.strip():
            gasto.iva_sobre_base = Decimal(iva_sobre_base_str)

        if numero_nota_credito and numero_nota_credito.strip():
            gasto.numero_nota_credito = numero_nota_credito

        if valor_nota_credito_str and valor_nota_credito_str.strip():
            gasto.valor_nota_credito = Decimal(valor_nota_credito_str)
            # Calculate monto_pendiente if nota de crédito exists
            gasto.monto_pendiente = valor_gastos_aduana - Decimal(valor_nota_credito_str)
        else:
            gasto.monto_pendiente = valor_gastos_aduana

        # Save the gasto first (without PDF)
        gasto.save()

        # Add pedidos
        pedidos_ids = request.POST.getlist('pedidos')
        for pedido_id in pedidos_ids:
            pedido = get_object_or_404(Pedido, id=pedido_id)
            gasto.pedidos.add(pedido)

        # Save PDF file if provided (upload_to will use the first pedido's fecha_entrega)
        if pdf_file:
            pdf_filename = f"aduana_manual_{numero_factura.replace('/', '_')}_{pdf_file.name}"
            gasto.pdf_file.save(pdf_filename, ContentFile(pdf_file.read()), save=True)

        # Save PDF rectificativa file if provided
        pdf_file_rectificativa = request.FILES.get('pdf_file_rectificativa')
        if pdf_file_rectificativa:
            pdf_filename_rect = f"aduana_rect_manual_{numero_factura.replace('/', '_')}_{pdf_file_rectificativa.name}"
            gasto.pdf_file_rectificativa.save(pdf_filename_rect, ContentFile(pdf_file_rectificativa.read()), save=True)

        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Error al crear gasto manual: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})