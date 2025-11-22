import os
import re
import logging
import io
from decimal import Decimal

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django import forms
from django.core.files.base import ContentFile
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

import pdfplumber

from .models import GastosCarga, AgenciaCarga, Pedido

# Setup logging
logger = logging.getLogger(__name__)

class PDFUploadForm(forms.Form):
    pdf_file = forms.FileField(label='Selecciona un archivo PDF')


def parse_amount(amount_str):
    """
    Convierte una cadena de número (1.234,56 o 1234,56) a Decimal.
    Asume formato europeo (coma para decimales) si hay ambigüedad o mezcla.
    """
    if not amount_str:
        return None

    # Limpiar caracteres no numéricos excepto . y ,
    clean_str = re.sub(r'[^\d.,]', '', str(amount_str))

    if ',' in clean_str and '.' in clean_str:
        # Formato 1.234,56 -> 1234.56
        clean_str = clean_str.replace('.', '').replace(',', '.')
    elif ',' in clean_str:
        # Formato 1234,56 -> 1234.56
        clean_str = clean_str.replace(',', '.')

    try:
        return Decimal(clean_str)
    except:
        return None


def extract_invoice_data_with_pdfplumber(pdf_content):
    """
    Extrae datos de la factura usando pdfplumber (local)
    """
    try:
        text_content = ""

        # Abrir el PDF desde el contenido en memoria
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            for page in pdf.pages:
                # Usamos extract_text() simple para obtener el flujo de texto
                page_text = page.extract_text()
                if page_text:
                    text_content += page_text + "\n"

        logger.info(f"[CARGA] Texto extraído (primeros 500 caracteres): {text_content[:500]}...")

        # 1. Agencia de Carga
        agencia_match = re.search(r'VIC VALCARGO INTERNACIONAL SAS', text_content, re.IGNORECASE)
        agencia_carga_name = agencia_match.group(0) if agencia_match else "No encontrado"
        logger.info(f"[CARGA] Agencia de Carga: {agencia_carga_name}")

        # 2. Número de Factura
        # Busca patrones como "No. VVL 15013" o "N.º VVL 12159"
        numero_factura = None
        factura_match = re.search(r'(?:N\.º|No\.|No)?\s*VVL\s*(\d+)', text_content, re.IGNORECASE)
        if factura_match:
            numero_factura = factura_match.group(1)
        else:
            # Intento alternativo solo buscando VVL seguido de números
            factura_match = re.search(r'VVL\s*(\d+)', text_content, re.IGNORECASE)
            if factura_match:
                numero_factura = factura_match.group(1)
            else:
                numero_factura = "No encontrado"

        logger.info(f"[CARGA] Número de Factura: {numero_factura}")

        # 3. AWBs
        # Busca MAWB o AWB seguido de patrón 123-12345678
        pedidos_matches = []
        # Patrón específico con prefijo
        awb_matches_context = re.findall(r'(?:MAWB|AWB)[:\s]*(\d{3}[-\s]*\d{8})', text_content, re.IGNORECASE)
        pedidos_matches.extend([awb.replace(" ", "").replace("--", "-") for awb in awb_matches_context])

        # Si no encuentra con contexto, busca el patrón numérico estricto 729-XXXXXXX (común en estos docs)
        # O patrón general 3 digitos - 8 digitos
        if not pedidos_matches:
            awb_matches_general = re.findall(r'(?<!\d)(\d{3}[-\s]\d{8})(?!\d)', text_content)
            pedidos_matches.extend([awb.replace(" ", "").replace("--", "-") for awb in awb_matches_general])

        # Eliminar duplicados manteniendo orden
        pedidos_matches = list(dict.fromkeys(pedidos_matches))

        logger.info(f"[CARGA] AWBs encontrados: {pedidos_matches}")
        logger.info(f"[CARGA] Total de AWBs: {len(pedidos_matches)}")

        # 4. Valor Gastos Carga
        # Busca "Total a Pagar USD" o similar
        valor_gastos_carga = None

        # Patrón 1: Total a Pagar USD ... valor
        # Ejemplo: "Total a Pagar USD 639,87"
        valor_pattern = r'Total\s*a\s*Pagar\s*(?:USD)?[\s\S]*?([\d.,]+)'
        valor_match = re.search(valor_pattern, text_content, re.IGNORECASE)

        if valor_match:
            valor_gastos_carga = parse_amount(valor_match.group(1))

        # Patrón 2: Buscar "Total Factura" o "Total (USD)"
        if not valor_gastos_carga:
            valor_match = re.search(r'Total\s*(?:Factura)?\s*\(?USD\)?\s*[:\s]*([\d.,]+)', text_content, re.IGNORECASE)
            if valor_match:
                valor_gastos_carga = parse_amount(valor_match.group(1))

        # Si no se encuentra, establecer como 0
        if valor_gastos_carga is None:
            valor_gastos_carga = Decimal('0.0')
            logger.warning(f"[CARGA] No se pudo extraer el valor de gastos de carga")

        logger.info(f"[CARGA] Valor Gastos Carga: {valor_gastos_carga}")

        return {
            'text': text_content,
            'extracted': {
                'agencia_carga': agencia_carga_name,
                'numero_factura': numero_factura,
                'awbs': pedidos_matches,
                'valor_gastos_carga': valor_gastos_carga
            }
        }

    except Exception as e:
        logger.error(f"[CARGA] Error al procesar documento con pdfplumber: {str(e)}")
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
                result = extract_invoice_data_with_pdfplumber(pdf_content)

                # Extraer valores del resultado
                agencia_carga_name = result['extracted']['agencia_carga']
                numero_factura = result['extracted']['numero_factura']
                pedidos_matches = result['extracted']['awbs']
                valor_gastos_carga = result['extracted']['valor_gastos_carga']

                # Validar que se hayan extraído los datos necesarios
                if agencia_carga_name == "No encontrado":
                    return JsonResponse({
                        'success': False,
                        'error': 'No se pudo identificar la agencia de carga en el PDF'
                    })

                if numero_factura == "No encontrado":
                    return JsonResponse({
                        'success': False,
                        'error': 'No se pudo identificar el número de factura en el PDF'
                    })

                # Extraer conceptos (simplificado)
                conceptos_text = f"Factura procesada con pdfplumber - Agencia: {agencia_carga_name}"

            except Exception as e:
                logger.error(f"Error al procesar con pdfplumber: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Error al procesar el PDF: {str(e)}'
                })

            # Get or create AgenciaCarga instance
            agencia, created = AgenciaCarga.objects.get_or_create(nombre=agencia_carga_name)

            # Verificar si ya existe un gasto con este número de factura
            existing_gasto = GastosCarga.objects.filter(numero_factura=numero_factura).first()
            if existing_gasto:
                # Obtener información de los pedidos asociados
                pedidos_info = ", ".join([p.awb for p in existing_gasto.pedidos.all()[:3]])
                if existing_gasto.pedidos.count() > 3:
                    pedidos_info += f" (y {existing_gasto.pedidos.count() - 3} más)"

                return JsonResponse({
                    'success': False,
                    'error': f'Ya existe un gasto registrado con el número de factura {numero_factura}. '
                            f'Agencia: {existing_gasto.agencia_carga.nombre}. '
                            f'Valor: ${existing_gasto.valor_gastos_carga} USD. '
                            f'AWBs asociados: {pedidos_info if pedidos_info else "Ninguno"}.'
                })

            # Get Pedido instances using the AWB field
            try:
                # We'll collect all the pedidos that match our list of AWBs
                matching_pedidos = []

                for awb in pedidos_matches:
                    # The AWB is already in the correct format, no need to format it
                    pedidos = Pedido.objects.filter(awb=awb)
                    if pedidos.exists():
                        matching_pedidos.extend(pedidos)

                if not matching_pedidos:
                    return JsonResponse({
                        'success': False,
                        'error': f'No se encontraron pedidos con los AWBs proporcionados: {pedidos_matches}'
                    })

            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Error al buscar pedidos: {str(e)}'
                })

            # Create GastosCarga instance
            try:
                gastos = GastosCarga(
                    agencia_carga=agencia,
                    numero_factura=numero_factura,
                    valor_gastos_carga=valor_gastos_carga,
                    conceptos=conceptos_text,
                )

                # Save the gasto first (without PDF)
                gastos.save()

                # Add all found pedidos to the gastos
                for pedido in matching_pedidos:
                    gastos.pedidos.add(pedido)

                # Guardar el archivo PDF (upload_to will use the first pedido's fecha_entrega)
                if pdf_file:
                    # Generar un nombre de archivo único basado en el número de factura
                    pdf_filename = f"carga_{numero_factura.replace('/', '_')}_{pdf_file.name}"
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
                    'error': f'Error al guardar GastosCarga: {str(e)}'
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
    gastos_list = GastosCarga.objects.all().order_by('-id')
    if numero_factura_query:
        gastos_list = gastos_list.filter(numero_factura__icontains=numero_factura_query)
    if semana_query:
        gastos_list = gastos_list.filter(pedidos__semana=semana_query).distinct()
    paginator = Paginator(gastos_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    semanas = Pedido.objects.values_list('semana', flat=True).distinct().order_by('semana')
    # --- Fin: filtros y paginación ---

    agencias = AgenciaCarga.objects.all()
    pedidos_disponibles = Pedido.objects.all()
    logger.info(f"Cantidad de pedidos disponibles: {pedidos_disponibles.count()}")

    return render(request, 'carga/upload_pdf_carga.html', {
        'form': form,
        'page_obj': page_obj,
        'numero_factura_query': numero_factura_query,
        'semana_query': semana_query,
        'semanas': semanas,
        'agencias': agencias,
        'pedidos_disponibles': pedidos_disponibles
    })


@login_required
@require_http_methods(["GET"])
def get_gasto(request, gasto_id):
    try:
        logger.info(f"Intentando obtener gasto con ID: {gasto_id}")
        gasto = get_object_or_404(GastosCarga, id=gasto_id)
        logger.info(f"Gasto encontrado: {gasto}")

        data = {
            'id': gasto.id,
            'numero_factura': gasto.numero_factura,
            'agencia_carga': gasto.agencia_carga.nombre,
            'agencia_carga_id': gasto.agencia_carga.id,
            'valor_gastos_carga': str(gasto.valor_gastos_carga),
            'valor_gastos_carga_eur': str(gasto.valor_gastos_carga_eur) if gasto.valor_gastos_carga_eur else None,
            'numero_nota_credito': gasto.numero_nota_credito,
            'valor_nota_credito': str(gasto.valor_nota_credito) if gasto.valor_nota_credito else None,
            'monto_pendiente': str(gasto.monto_pendiente) if gasto.monto_pendiente else None,
            'pagado': gasto.pagado,
            'pedidos': [f"{pedido.id} - {str(pedido)}" for pedido in gasto.pedidos.all()],
            'pedidos_ids': [pedido.id for pedido in gasto.pedidos.all()],
            'pdf_file': gasto.pdf_file.url if gasto.pdf_file else None,
            'pdf_file_rectificativa': gasto.pdf_file_rectificativa.url if gasto.pdf_file_rectificativa else None
        }
        logger.info(f"Datos preparados para respuesta: {data}")
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Error al obtener gasto: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def update_gasto(request, gasto_id):
    gasto = get_object_or_404(GastosCarga, id=gasto_id)
    try:
        gasto.numero_factura = request.POST.get('numero_factura')
        gasto.valor_gastos_carga = Decimal(request.POST.get('valor_gastos_carga'))

        # Procesar los campos de nota de crédito
        numero_nota_credito = request.POST.get('numero_nota_credito')
        if numero_nota_credito:
            gasto.numero_nota_credito = numero_nota_credito
        else:
            gasto.numero_nota_credito = None

        valor_nota_credito = request.POST.get('valor_nota_credito')
        if valor_nota_credito and valor_nota_credito.strip():
            gasto.valor_nota_credito = Decimal(valor_nota_credito)
            gasto.monto_pendiente = gasto.valor_gastos_carga - Decimal(valor_nota_credito)
        else:
            gasto.valor_nota_credito = None
            gasto.monto_pendiente = gasto.valor_gastos_carga

        # Actualizar pedidos asociados
        pedidos_ids = request.POST.getlist('pedidos')
        gasto.pedidos.clear()  # Eliminar asociaciones existentes
        for pedido_id in pedidos_ids:
            pedido = get_object_or_404(Pedido, id=pedido_id)
            gasto.pedidos.add(pedido)

        gasto.save()

        # Handle PDF file if provided
        pdf_file = request.FILES.get('pdf_file')
        if pdf_file:
            pdf_filename = f"carga_edit_{gasto.numero_factura.replace('/', '_')}_{pdf_file.name}"
            gasto.pdf_file.save(pdf_filename, ContentFile(pdf_file.read()), save=True)

        # Handle PDF rectificativa file if provided
        pdf_file_rectificativa = request.FILES.get('pdf_file_rectificativa')
        if pdf_file_rectificativa:
            pdf_filename_rect = f"carga_rect_{gasto.numero_factura.replace('/', '_')}_{pdf_file_rectificativa.name}"
            gasto.pdf_file_rectificativa.save(pdf_filename_rect, ContentFile(pdf_file_rectificativa.read()), save=True)

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_gasto(request, gasto_id):
    gasto = get_object_or_404(GastosCarga, id=gasto_id)
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
        agencia_id = request.POST.get('agencia_carga')
        numero_factura = request.POST.get('numero_factura')
        valor_gastos_carga = Decimal(request.POST.get('valor_gastos_carga'))
        numero_nota_credito = request.POST.get('numero_nota_credito', None)
        valor_nota_credito_str = request.POST.get('valor_nota_credito', '')

        # Get PDF file if provided
        pdf_file = request.FILES.get('pdf_file')

        # Get agencia
        agencia = get_object_or_404(AgenciaCarga, id=agencia_id)

        # Create gasto
        gasto = GastosCarga(
            agencia_carga=agencia,
            numero_factura=numero_factura,
            valor_gastos_carga=valor_gastos_carga,
            numero_nota_credito=numero_nota_credito if numero_nota_credito else None
        )

        # Process nota credito if provided
        if valor_nota_credito_str and valor_nota_credito_str.strip():
            valor_nota_credito = Decimal(valor_nota_credito_str)
            gasto.valor_nota_credito = valor_nota_credito
            gasto.monto_pendiente = valor_gastos_carga - valor_nota_credito
        else:
            gasto.monto_pendiente = valor_gastos_carga

        # Save the gasto first (without PDF)
        gasto.save()

        # Add pedidos
        pedidos_ids = request.POST.getlist('pedidos')
        for pedido_id in pedidos_ids:
            pedido = get_object_or_404(Pedido, id=pedido_id)
            gasto.pedidos.add(pedido)

        # Save PDF file if provided (upload_to will use the first pedido's fecha_entrega)
        if pdf_file:
            pdf_filename = f"carga_manual_{numero_factura.replace('/', '_')}_{pdf_file.name}"
            gasto.pdf_file.save(pdf_filename, ContentFile(pdf_file.read()), save=True)

        # Save PDF rectificativa file if provided
        pdf_file_rectificativa = request.FILES.get('pdf_file_rectificativa')
        if pdf_file_rectificativa:
            pdf_filename_rect = f"carga_rect_manual_{numero_factura.replace('/', '_')}_{pdf_file_rectificativa.name}"
            gasto.pdf_file_rectificativa.save(pdf_filename_rect, ContentFile(pdf_file_rectificativa.read()), save=True)

        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Error al crear gasto manual: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})