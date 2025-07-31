from io import BytesIO

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, JsonResponse
from django import forms
from django.core.validators import MinValueValidator
from decimal import Decimal
from pdfminer.high_level import extract_text
import re
import logging
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import GastosCarga, AgenciaCarga, Pedido

# Setup logging
logger = logging.getLogger(__name__)

class PDFUploadForm(forms.Form):
    pdf_file = forms.FileField(label='Selecciona un archivo PDF')


@login_required
def process_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = form.cleaned_data['pdf_file']
            pdf_file.seek(0)  # Reiniciar puntero
            
            # Convertir el contenido a un objeto de archivo binario
            pdf_content = pdf_file.read()
            text = extract_text(BytesIO(pdf_content))
            
            # Extract agencia_carga (fixed value from the PDF content)
            agencia_carga_match = re.search(r'VIC VALCARGO INTERNACIONAL SAS', text)
            agencia_carga_name = agencia_carga_match.group(0) if agencia_carga_match else None

            # Extract numero_factura
            numero_factura_match = re.search(r'N\.º VVL (\d+)', text)
            numero_factura = numero_factura_match.group(1) if numero_factura_match else None

            # Extract pedidos (AWB numbers) with optional spaces after the dash
            pedidos_matches = re.findall(r'MAWB:\s*(\d+-\s*\d+)', text)
            # Normalize AWB values by removing spaces
            pedidos_matches = [awb.replace(" ", "") for awb in pedidos_matches]
            
            # Extract valor_gastos_carga
            valor_pattern = r'Total a Pagar USD[\s\S]*?([\d.,]+)'
            bruto_pattern = r'Bruto total[\s\S]*?([\d.,]+)'

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
                else:
                    valor_gastos_carga = Decimal('0.0')

            # Extract conceptos (tabla)
            # Procesamiento de conceptos
            conceptos = []
            lines = [line.strip() for line in text.split('\n') if line.strip()]

            # Buscar inicio de la tabla después de los encabezados
            table_start = None
            for i in range(len(lines)):
                if lines[i] == 'Artículo' and i + 4 < len(lines):
                    if (lines[i + 1] == 'Descripción' and
                            lines[i + 2] == 'Cantidad' and
                            lines[i + 3] == 'Vr. Unitario' and
                            lines[i + 4] == 'Vr. Bruto'):
                        table_start = i + 5  # Saltar encabezados
                        break

            if table_start is not None:
                i = table_start
                while i < len(lines):
                    if lines[i].isdigit():
                        try:
                            # Capturar los 5 componentes de cada fila
                            articulo = lines[i]
                            descripcion = lines[i + 1]
                            cantidad = lines[i + 2]
                            vr_unitario = lines[i + 3]
                            vr_bruto = lines[i + 4]

                            # Formatear concepto
                            concepto = (
                                f"{descripcion} - "
                                f"Cant: {cantidad}, "
                                f"Vr. Unitario: {vr_unitario}, "
                                f"Total: {vr_bruto}"
                            )
                            conceptos.append(concepto)
                            i += 5  # Saltar 5 líneas procesadas
                        except IndexError:
                            break  # Fin de la tabla
                    else:
                        i += 1

            conceptos_text = "\n".join(conceptos)[:500]

            # Get or create AgenciaCarga instance
            agencia, created = AgenciaCarga.objects.get_or_create(nombre=agencia_carga_name)

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
                        'error': f'No se encontraron pedidos con los AWBs proporcionados'
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
                gastos.save()
                
                # Add all found pedidos to the gastos
                for pedido in matching_pedidos:
                    gastos.pedidos.add(pedido)
                
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
        
        # Obtener todos los pedidos disponibles para el select en el modal de edición
        pedidos_disponibles = list(Pedido.objects.all().values('id', 'awb'))
        pedidos_asociados = list(gasto.pedidos.values_list('id', flat=True))
        
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
            'pedidos_ids': pedidos_asociados,
            'pedidos_disponibles': pedidos_disponibles,
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
            # Calcular monto pendiente
            gasto.monto_pendiente = gasto.valor_gastos_carga - Decimal(valor_nota_credito)
        else:
            gasto.valor_nota_credito = None
            gasto.monto_pendiente = gasto.valor_gastos_carga

        # Actualizar pedidos asociados si se envían
        pedidos_ids = request.POST.getlist('pedidos')
        if pedidos_ids:
            gasto.pedidos.set(pedidos_ids)
        
        gasto.save()
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
        
        gasto.save()
        
        # Add pedidos
        pedidos_ids = request.POST.getlist('pedidos')
        for pedido_id in pedidos_ids:
            pedido = get_object_or_404(Pedido, id=pedido_id)
            gasto.pedidos.add(pedido)
        
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Error al crear gasto manual: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})