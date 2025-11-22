import os
import re
import logging
from decimal import Decimal

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django import forms
from django.core.files.base import ContentFile
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

# Google Document AI imports
from google.cloud import documentai_v1
from google.api_core.client_options import ClientOptions

from .models import GastosCarga, AgenciaCarga, Pedido

# Setup logging
logger = logging.getLogger(__name__)

class PDFUploadForm(forms.Form):
    pdf_file = forms.FileField(label='Selecciona un archivo PDF')


def extract_invoice_data_with_docai(pdf_content):
    """
    Extrae datos de la factura usando Google Document AI
    """
    try:
        # Obtener credenciales desde variables de entorno
        project_id = os.getenv('GCP_PROJECT_ID')
        location = os.getenv('GCP_LOCATION')
        processor_id = os.getenv('GCP_INVOICE_PROCESSOR_ID')

        if not all([project_id, location, processor_id]):
            raise ValueError("Faltan variables de entorno de Google Cloud (GCP_PROJECT_ID, GCP_LOCATION, GCP_INVOICE_PROCESSOR_ID)")

        # Configurar el cliente de Document AI
        opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
        client = documentai_v1.DocumentProcessorServiceClient(client_options=opts)

        # Nombre completo del procesador
        name = client.processor_path(project_id, location, processor_id)

        # Crear el documento raw
        raw_document = documentai_v1.RawDocument(
            content=pdf_content,
            mime_type="application/pdf"
        )

        # Crear la solicitud de procesamiento
        request = documentai_v1.ProcessRequest(
            name=name,
            raw_document=raw_document
        )

        # Procesar el documento
        result = client.process_document(request=request)
        document = result.document

        # Extraer datos de las entidades
        extracted_data = {
            'text': document.text,
            'entities': {}
        }

        # Procesar entidades extraídas
        for entity in document.entities:
            entity_type = entity.type_
            entity_value = entity.mention_text
            extracted_data['entities'][entity_type] = entity_value
            logger.info(f"Entidad encontrada: {entity_type} = {entity_value}")

        return extracted_data

    except Exception as e:
        logger.error(f"Error al procesar documento con Document AI: {str(e)}")
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
                # Extraer datos usando Google Document AI
                doc_data = extract_invoice_data_with_docai(pdf_content)
                text = doc_data['text']
                entities = doc_data['entities']

                logger.info(f"Texto extraído: {text[:500]}...")
                logger.info(f"Entidades extraídas: {entities}")

                # Extraer agencia_carga
                # Buscar en entidades primero, luego en texto
                agencia_carga_name = entities.get('supplier_name', None)
                if not agencia_carga_name:
                    agencia_carga_match = re.search(r'VIC VALCARGO INTERNACIONAL SAS', text, re.IGNORECASE)
                    agencia_carga_name = agencia_carga_match.group(0) if agencia_carga_match else "VIC VALCARGO INTERNACIONAL SAS"

                # Extraer numero_factura
                numero_factura = entities.get('invoice_id', None)
                if numero_factura:
                    # Limpiar el número de factura (quitar prefijo VVL si existe)
                    numero_factura_match = re.search(r'(?:VVL\s*)?(\d+)', numero_factura, re.IGNORECASE)
                    numero_factura = numero_factura_match.group(1) if numero_factura_match else numero_factura
                else:
                    # Buscar patrón VVL seguido de números
                    numero_factura_match = re.search(r'(?:N\.º\s*)?VVL\s*(\d+)', text, re.IGNORECASE)
                    numero_factura = numero_factura_match.group(1) if numero_factura_match else None

                # Extraer AWB (pedidos)
                pedidos_matches = []
                # Buscar específicamente AWBs con el contexto "MAWB:" para mayor precisión
                awb_matches = re.findall(r'MAWB:?\s*(\d{3}[-\s]*\d{8})', text, re.IGNORECASE)
                pedidos_matches = [awb.replace(" ", "").replace("--", "-") for awb in awb_matches]

                # Si no se encontraron con MAWB, buscar patrón más general pero con contexto
                if not pedidos_matches:
                    # Buscar líneas que contengan "MAWB" o "AWB" seguido del número
                    for line in text.split('\n'):
                        if 'MAWB' in line.upper() or 'AWB' in line.upper():
                            awb_in_line = re.findall(r'(\d{3}[-\s]*\d{8})', line)
                            pedidos_matches.extend([awb.replace(" ", "") for awb in awb_in_line])

                # Eliminar duplicados manteniendo el orden
                pedidos_matches = list(dict.fromkeys(pedidos_matches))

                logger.info(f"AWBs encontrados: {pedidos_matches}")

                # Extraer valor_gastos_carga
                valor_gastos_carga = Decimal('0.0')

                # Intentar obtener el total de las entidades (priorizar net_amount)
                total_amount = entities.get('net_amount', None) or entities.get('total_amount', None)
                if total_amount:
                    # Limpiar el valor (quitar símbolos de moneda, espacios, etc.)
                    valor_str = re.sub(r'[^\d.,]', '', str(total_amount))
                    # Convertir formato europeo (1.234,56) a formato decimal (1234.56)
                    if ',' in valor_str and '.' in valor_str:
                        # Formato: 1.234,56 -> 1234.56
                        valor_str = valor_str.replace('.', '').replace(',', '.')
                    elif ',' in valor_str:
                        # Formato: 1234,56 -> 1234.56
                        valor_str = valor_str.replace(',', '.')

                    try:
                        valor_gastos_carga = Decimal(valor_str)
                    except:
                        logger.warning(f"No se pudo convertir el valor: {valor_str}")

                # Si no se encontró en entidades, buscar en el texto
                if valor_gastos_carga == Decimal('0.0'):
                    valor_pattern = r'Total\s*a\s*Pagar\s*USD[\s\S]*?([\d.,]+)'
                    bruto_pattern = r'Bruto\s*total[\s\S]*?([\d.,]+)'

                    valor_match = re.search(valor_pattern, text, re.IGNORECASE)
                    if valor_match:
                        valor_str_raw = valor_match.group(1).strip()
                        if ',' in valor_str_raw:
                            valor_str = valor_str_raw.replace('.', '').replace(',', '.')
                        else:
                            valor_str = valor_str_raw
                        valor_gastos_carga = Decimal(valor_str)
                    else:
                        bruto_match = re.search(bruto_pattern, text, re.IGNORECASE)
                        if bruto_match:
                            valor_str_raw = bruto_match.group(1).strip()
                            if ',' in valor_str_raw:
                                valor_str = valor_str_raw.replace('.', '').replace(',', '.')
                            else:
                                valor_str = valor_str_raw
                            valor_gastos_carga = Decimal(valor_str)

                logger.info(f"Valor gastos carga: {valor_gastos_carga}")

                # Extraer conceptos (simplificado)
                conceptos_text = f"Factura procesada con Document AI - Agencia: {agencia_carga_name}"

            except Exception as e:
                logger.error(f"Error al procesar con Document AI: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Error al procesar el PDF con Document AI: {str(e)}'
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