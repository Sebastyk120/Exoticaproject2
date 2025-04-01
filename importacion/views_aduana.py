from io import BytesIO
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, JsonResponse
from django import forms
from django.core.validators import MinValueValidator
from decimal import Decimal
from pdfminer.high_level import extract_text
import re
from .models import GastosAduana, AgenciaAduana, Pedido
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required


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

            # Create GastosAduana instance
            try:
                gastos = GastosAduana(
                    agencia_aduana=agencia,
                    numero_factura=numero_factura,
                    valor_gastos_aduana=valor_gastos_aduana,
                    conceptos=conceptos_text,
                )
                gastos.save()
                
                # Agregar todos los pedidos encontrados
                for pedido in pedidos:
                    gastos.pedidos.add(pedido)
                
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

    # Get all gastos for the table
    gastos = GastosAduana.objects.all().order_by('-id')
    return render(request, 'aduana/upload_pdf_aduana.html', {
        'form': form,
        'gastos': gastos
    })


@login_required
@require_http_methods(["GET"])
def get_gasto(request, gasto_id):
    gasto = get_object_or_404(GastosAduana, id=gasto_id)
    data = {
        'id': gasto.id,
        'numero_factura': gasto.numero_factura,
        'agencia_aduana': gasto.agencia_aduana.nombre,
        'valor_gastos_aduana': str(gasto.valor_gastos_aduana),
        'numero_nota_credito': gasto.numero_nota_credito,
        'valor_nota_credito': str(gasto.valor_nota_credito) if gasto.valor_nota_credito else "",
        'monto_pendiente': str(gasto.monto_pendiente) if gasto.monto_pendiente else "",
        'pagado': gasto.pagado,
        'pedidos': [f"{pedido.id} - {str(pedido)}" for pedido in gasto.pedidos.all()]
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
            
        gasto.save()
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