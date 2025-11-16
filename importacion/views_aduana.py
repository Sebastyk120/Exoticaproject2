from io import BytesIO
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, JsonResponse
from django import forms
from django.core.validators import MinValueValidator
from django.core.files.base import ContentFile
from decimal import Decimal
from pdfminer.high_level import extract_text
import re
import logging
from .models import GastosAduana, AgenciaAduana, Pedido, get_upload_path_aduana
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

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
            
            # Extract agencia_aduana (fixed value from the PDF content)
            agencia_aduana_name = "Arola Aduanas y Consignaciones, S.L."

            # Extract numero_factura using regex
            numero_factura_match = re.search(r'(\d{2}-FV-\d{6})', text)
            numero_factura = numero_factura_match.group(1) if numero_factura_match else None

            # Verificar si ya existe un gasto con el mismo número de factura
            if numero_factura and GastosAduana.objects.filter(numero_factura=numero_factura).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'Ya existe un gasto con el número de factura: {numero_factura}'
                })

            # Extraer el número de pedido (mismo regex que antes)
            pedidos_match = re.search(r'AV\d+\/(\d+)\/\d+', text)
            pedidos_number = pedidos_match.group(1) if pedidos_match else None

            # Formatear el número con guion después de los 3 primeros dígitos
            if pedidos_number:
                formatted_pedido = f"{pedidos_number[:3]}-{pedidos_number[3:]}"
            else:
                formatted_pedido = None

            # Extract valor_gastos_aduana from "Total Factura(EUR) X"
            valor_match = re.search(r'Total Factura \(EUR\)[\s\S]*?(\d[\d.,]*)\s+Forma de Pago', text)
            if valor_match:
                valor_str_raw = valor_match.group(1).strip()
                if ',' in valor_str_raw:
                    valor_str = valor_str_raw.replace('.', '').replace(',', '.')
                else:
                    valor_str = valor_str_raw
                valor_gastos_aduana = Decimal(valor_str)
            else:
                valor_gastos_aduana = Decimal('0.0')

            # EXTRAER CONCEPTOS
            conceptos_match = re.search(r'CONCEPTOS[\s\S]*?(?=(Forma de Pago|Total Factura))', text)
            if conceptos_match:
                conceptos_text = conceptos_match.group(0).strip()
                # Limpiar el texto (quitar saltos de línea y espacios en exceso)
                conceptos_text = ' '.join(conceptos_text.split())
                # Truncar a 500 caracteres si es necesario
                if len(conceptos_text) > 500:
                    conceptos_text = conceptos_text[:497] + "..."
            else:
                conceptos_text = None

            # Get or create AgenciaAduana instance
            agencia, created = AgenciaAduana.objects.get_or_create(nombre=agencia_aduana_name)

            # Get Pedido instances using the AWB field
            try:
                # Buscar los pedidos usando el campo awb (pueden ser varios)
                pedidos = Pedido.objects.filter(awb=formatted_pedido)
                
                if not pedidos.exists():
                    return JsonResponse({
                        'success': False,
                        'error': f'No se encontraron pedidos con AWB: {formatted_pedido}'
                    })
                    
                pedidos_count = pedidos.count()
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Error al buscar pedidos: {str(e)}'
                })

            # Extraer IVA de Importación - método dinámico
            iva_importacion = Decimal('0.00')
            
            # Método 1: Buscar "IVA (Importación)" seguido por el valor
            pattern1 = r'IVA\s*\(\s*Importación\s*\).*?(\d+[.,]\d+)'
            iva_match1 = re.search(pattern1, text)
            if iva_match1:
                iva_importacion = Decimal(iva_match1.group(1).replace(',', '.'))
            else:
                # Método 2: Buscar "54 IVA" seguido por el valor
                pattern2 = r'54\s+IVA.*?(\d+[.,]\d+)'
                iva_match2 = re.search(pattern2, text)
                if iva_match2:
                    iva_importacion = Decimal(iva_match2.group(1).replace(',', '.'))
                else:
                    # Método 3: Buscar en la tabla, después de No IVA y antes de Total sujeto
                    pattern3 = r'No IVA.*?(\d+[.,]\d+)\s+Total sujeto'
                    iva_match3 = re.search(pattern3, text, re.DOTALL)
                    if iva_match3:
                        iva_importacion = Decimal(iva_match3.group(1).replace(',', '.'))

                
            # Extraer iva_sobre_base: buscar la línea que sigue a "IVA21" y comienza con "0"
            iva_sobre_base_pattern = r'IVA21\s*.*\n0\s+(\d{1,3}(?:\.\d{3})*,\d+)'
            iva_sobre_base_match = re.search(iva_sobre_base_pattern, text, re.DOTALL)
            if iva_sobre_base_match:
                iva_sobre_base_str = iva_sobre_base_match.group(1).replace('.', '').replace(',', '.')
                iva_sobre_base = Decimal(iva_sobre_base_str)
            else:
                iva_sobre_base = Decimal('0.00')

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
                primer_pedido = None
                for pedido in pedidos:
                    gastos.pedidos.add(pedido)
                    if primer_pedido is None:
                        primer_pedido = pedido

                # Guardar el archivo PDF usando la fecha del primer pedido
                if pdf_file and primer_pedido:
                    # Generar un nombre de archivo único basado en el número de factura
                    pdf_filename = f"aduana_{numero_factura.replace('/', '_')}_{pdf_file.name}"
                    pdf_path = get_upload_path_aduana(primer_pedido, pdf_filename)
                    # Reiniciar el puntero del archivo antes de guardarlo
                    pdf_file.seek(0)
                    gastos.pdf_file.save(pdf_path, pdf_file, save=True)

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
        'valor_gastos_aduana': str(gasto.valor_gastos_aduana),
        'numero_nota_credito': gasto.numero_nota_credito,
        'valor_nota_credito': str(gasto.valor_nota_credito) if gasto.valor_nota_credito else "",
        'monto_pendiente': str(gasto.monto_pendiente) if gasto.monto_pendiente else "",
        'pagado': gasto.pagado,
        'iva_importacion': str(gasto.iva_importacion) if gasto.iva_importacion else "0.00",
        'iva_sobre_base': str(gasto.iva_sobre_base) if gasto.iva_sobre_base else "0.00",
        'pedidos': [f"{pedido.id} - {str(pedido)}" for pedido in gasto.pedidos.all()],
        'semana': semana,
        'pdf_file': gasto.pdf_file.url if gasto.pdf_file else None
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
            primer_pedido = gasto.pedidos.first()
            pdf_filename = f"aduana_edit_{gasto.numero_factura.replace('/', '_')}_{pdf_file.name}"
            pdf_path = get_upload_path_aduana(primer_pedido, pdf_filename)
            gasto.pdf_file.save(pdf_path, pdf_file, save=True)
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
        primer_pedido = None
        for pedido_id in pedidos_ids:
            pedido = get_object_or_404(Pedido, id=pedido_id)
            gasto.pedidos.add(pedido)
            if primer_pedido is None:
                primer_pedido = pedido

        # Save PDF file if provided, using the first pedido's fecha_entrega
        if pdf_file and primer_pedido:
            pdf_filename = f"aduana_manual_{numero_factura.replace('/', '_')}_{pdf_file.name}"
            pdf_path = get_upload_path_aduana(primer_pedido, pdf_filename)
            gasto.pdf_file.save(pdf_path, pdf_file, save=True)

        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Error al crear gasto manual: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})