"""
Script de prueba para verificar la extracción de datos con Google Document AI
"""
import os
import re
from decimal import Decimal
from dotenv import load_dotenv
from google.cloud import documentai_v1
from google.api_core.client_options import ClientOptions

# Cargar variables de entorno
load_dotenv()

def extract_invoice_data_with_docai(pdf_path):
    """
    Extrae datos de la factura usando Google Document AI
    """
    try:
        # Obtener credenciales desde variables de entorno
        project_id = os.getenv('GCP_PROJECT_ID')
        location = os.getenv('GCP_LOCATION')
        processor_id = os.getenv('GCP_INVOICE_PROCESSOR_ID')
        
        print(f"Project ID: {project_id}")
        print(f"Location: {location}")
        print(f"Processor ID: {processor_id}")
        
        if not all([project_id, location, processor_id]):
            raise ValueError("Faltan variables de entorno de Google Cloud")
        
        # Configurar el cliente de Document AI
        opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
        client = documentai_v1.DocumentProcessorServiceClient(client_options=opts)
        
        # Nombre completo del procesador
        name = client.processor_path(project_id, location, processor_id)
        print(f"Processor path: {name}")
        
        # Leer el archivo PDF
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
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
        
        print("\nProcesando documento...")
        # Procesar el documento
        result = client.process_document(request=request)
        document = result.document
        
        print(f"\nTexto extraído (primeros 500 caracteres):")
        print(document.text[:500])
        print("\n" + "="*80)
        
        # Extraer datos de las entidades
        print("\nEntidades encontradas:")
        print("="*80)
        entities = {}
        for entity in document.entities:
            entity_type = entity.type_
            entity_value = entity.mention_text
            confidence = entity.confidence
            entities[entity_type] = entity_value
            print(f"  {entity_type}: {entity_value} (confianza: {confidence:.2%})")
        
        print("\n" + "="*80)
        print("\nExtracción de campos específicos:")
        print("="*80)
        
        # Extraer agencia_carga
        agencia_carga_name = entities.get('supplier_name', None)
        if not agencia_carga_name:
            agencia_carga_match = re.search(r'VIC VALCARGO INTERNACIONAL SAS', document.text, re.IGNORECASE)
            agencia_carga_name = agencia_carga_match.group(0) if agencia_carga_match else "No encontrado"
        print(f"Agencia de Carga: {agencia_carga_name}")
        
        # Extraer numero_factura
        numero_factura = entities.get('invoice_id', None)
        if numero_factura:
            # Limpiar el número de factura (quitar prefijo VVL si existe)
            numero_factura_match = re.search(r'(?:VVL\s*)?(\d+)', numero_factura, re.IGNORECASE)
            numero_factura = numero_factura_match.group(1) if numero_factura_match else numero_factura
        else:
            numero_factura_match = re.search(r'(?:N\.º\s*)?VVL\s*(\d+)', document.text, re.IGNORECASE)
            numero_factura = numero_factura_match.group(1) if numero_factura_match else "No encontrado"
        print(f"Número de Factura: {numero_factura}")
        
        # Extraer AWB (solo con contexto MAWB para mayor precisión)
        awb_matches = re.findall(r'MAWB:?\s*(\d{3}[-\s]*\d{8})', document.text, re.IGNORECASE)
        pedidos_matches = [awb.replace(" ", "").replace("--", "-") for awb in awb_matches]

        # Si no se encontraron con MAWB, buscar patrón más general pero con contexto
        if not pedidos_matches:
            for line in document.text.split('\n'):
                if 'MAWB' in line.upper() or 'AWB' in line.upper():
                    awb_in_line = re.findall(r'(\d{3}[-\s]*\d{8})', line)
                    pedidos_matches.extend([awb.replace(" ", "") for awb in awb_in_line])

        # Eliminar duplicados manteniendo el orden
        pedidos_matches = list(dict.fromkeys(pedidos_matches))

        print(f"AWBs encontrados: {pedidos_matches}")
        print(f"Total de AWBs: {len(pedidos_matches)}")
        
        # Extraer valor_gastos_carga (priorizar net_amount)
        total_amount = entities.get('net_amount', None) or entities.get('total_amount', None)
        if total_amount:
            valor_str = re.sub(r'[^\d.,]', '', str(total_amount))
            if ',' in valor_str and '.' in valor_str:
                valor_str = valor_str.replace('.', '').replace(',', '.')
            elif ',' in valor_str:
                valor_str = valor_str.replace(',', '.')
            try:
                valor_gastos_carga = Decimal(valor_str)
            except:
                valor_gastos_carga = "Error al convertir"
        else:
            # Buscar en el texto
            valor_pattern = r'Total\s*a\s*Pagar\s*USD[\s\S]*?([\d.,]+)'
            valor_match = re.search(valor_pattern, document.text, re.IGNORECASE)
            if valor_match:
                valor_str_raw = valor_match.group(1).strip()
                if ',' in valor_str_raw:
                    valor_str = valor_str_raw.replace('.', '').replace(',', '.')
                else:
                    valor_str = valor_str_raw
                valor_gastos_carga = Decimal(valor_str)
            else:
                valor_gastos_carga = "No encontrado"
        
        print(f"Valor Gastos Carga: {valor_gastos_carga}")
        
        print("\n" + "="*80)
        print("\nValores esperados (según el ejemplo):")
        print("="*80)
        print("Número de Factura: 12159")
        print("Agencia de Carga: VIC VALCARGO INTERNACIONAL SAS")
        print("AWB: 729-45243995")
        print("Valor Gastos Carga: 639.87")
        
        return {
            'text': document.text,
            'entities': entities,
            'extracted': {
                'agencia_carga': agencia_carga_name,
                'numero_factura': numero_factura,
                'awbs': pedidos_matches,
                'valor_gastos_carga': valor_gastos_carga
            }
        }
        
    except Exception as e:
        print(f"\nError al procesar documento: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    pdf_path = "VVL 15013.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Error: No se encuentra el archivo {pdf_path}")
        print(f"Directorio actual: {os.getcwd()}")
    else:
        print(f"Procesando archivo: {pdf_path}")
        print("="*80)
        result = extract_invoice_data_with_docai(pdf_path)

