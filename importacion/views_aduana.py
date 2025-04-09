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
        'iva_importacion': str(gasto.iva_importacion) if gasto.iva_importacion else "0.00",
        'iva_sobre_base': str(gasto.iva_sobre_base) if gasto.iva_sobre_base else "0.00",
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
            
        # Add IVA fields to update process
        iva_importacion = request.POST.get('iva_importacion')
        if iva_importacion and iva_importacion.strip():
            gasto.iva_importacion = Decimal(iva_importacion)
        
        iva_sobre_base = request.POST.get('iva_sobre_base')
        if iva_sobre_base and iva_sobre_base.strip():
            gasto.iva_sobre_base = Decimal(iva_sobre_base)
            
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