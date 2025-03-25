from io import BytesIO

from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django import forms
from django.core.validators import MinValueValidator
from decimal import Decimal
from pdfminer.high_level import extract_text
import re


class PDFUploadForm(forms.Form):
    pdf_file = forms.FileField(label='Selecciona un archivo PDF')


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
                valor_str = valor_match.group(1).replace('.', '').replace(',', '.')
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
            from .models import AgenciaAduana
            agencia, created = AgenciaAduana.objects.get_or_create(nombre=agencia_aduana_name)

            # Get Pedido instances using the AWB field
            from .models import Pedido
            try:
                # Buscar los pedidos usando el campo awb (pueden ser varios)
                pedidos = Pedido.objects.filter(awb=formatted_pedido)
                
                if not pedidos.exists():
                    return render(request, 'aduana/upload_pdf_aduana.html', {
                        'form': form,
                        'error': f'No se encontraron pedidos con AWB: {formatted_pedido}'
                    })
                    
                pedidos_count = pedidos.count()
                
            except Exception as e:
                return render(request, 'aduana/upload_pdf_aduana.html', {
                    'form': form,
                    'error': f'Error al buscar pedidos: {str(e)}'
                })

            # Create GastosAduana instance
            from .models import GastosAduana
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
                
            except Exception as e:
                return render(request, 'aduana/upload_pdf_aduana.html', {
                    'form': form,
                    'error': f'Error al guardar GastosAduana: {str(e)}'
                })

            return HttpResponseRedirect('/aduana_pdf/')
    else:
        form = PDFUploadForm()

    return render(request, 'aduana/upload_pdf_aduana.html', {'form': form})