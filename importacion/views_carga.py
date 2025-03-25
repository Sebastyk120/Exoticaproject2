from io import BytesIO

from django.shortcuts import render
from django.http import HttpResponseRedirect
from django import forms
from django.core.validators import MinValueValidator
from decimal import Decimal
from pdfminer.high_level import extract_text
import re
import logging

# Setup logging
logger = logging.getLogger(__name__)

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
            
            # Extract agencia_carga (fixed value from the PDF content)
            agencia_carga_match = re.search(r'VIC VALCARGO INTERNACIONAL SAS', text)
            agencia_carga_name = agencia_carga_match.group(0) if agencia_carga_match else None

            # Extract numero_factura
            numero_factura_match = re.search(r'N\.º VVL (\d+)', text)
            numero_factura = numero_factura_match.group(1) if numero_factura_match else None

            # Extract pedidos (AWB numbers)
            pedidos_matches = re.findall(r'MAWB: (\d+-\d+)', text)
            
            # Extract valor_gastos_carga
            valor_pattern = r'Total a Pagar USD[\s\S]*?([\d.,]+)'
            bruto_pattern = r'Bruto total[\s\S]*?([\d.,]+)'

            valor_match = re.search(valor_pattern, text, re.IGNORECASE)
            if valor_match:
                valor_str = valor_match.group(1).replace(',', '')
                valor_gastos_carga = Decimal(valor_str)
            else:
                bruto_match = re.search(bruto_pattern, text, re.IGNORECASE)
                if bruto_match:
                    valor_str = bruto_match.group(1).replace(',', '')
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
            from .models import AgenciaCarga
            agencia, created = AgenciaCarga.objects.get_or_create(nombre=agencia_carga_name)

            # Get Pedido instances using the AWB field
            from .models import Pedido
            try:
                # We'll collect all the pedidos that match our list of AWBs
                matching_pedidos = []
                
                for awb in pedidos_matches:
                    # The AWB is already in the correct format, no need to format it
                    pedidos = Pedido.objects.filter(awb=awb)
                    if pedidos.exists():
                        matching_pedidos.extend(pedidos)
                
                if not matching_pedidos:
                    return render(request, 'carga/upload_pdf_carga.html', {
                        'form': form,
                        'error': f'No se encontraron pedidos con los AWBs proporcionados'
                    })
                    
            except Exception as e:
                return render(request, 'carga/upload_pdf_carga.html', {
                    'form': form,
                    'error': f'Error al buscar pedidos: {str(e)}'
                })

            # Create GastosCarga instance
            from .models import GastosCarga
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
                
            except Exception as e:
                return render(request, 'carga/upload_pdf_carga.html', {
                    'form': form,
                    'error': f'Error al guardar GastosCarga: {str(e)}'
                })

            return HttpResponseRedirect('/carga_pdf/')
    else:
        form = PDFUploadForm()

    return render(request, 'carga/upload_pdf_carga.html', {'form': form})