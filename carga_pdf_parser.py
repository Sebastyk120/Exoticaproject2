"""
Script de prueba para verificar la extracción de datos con pdfplumber
Reemplaza la implementación anterior de Google Document AI
"""
import os
import re
import pdfplumber
from decimal import Decimal

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

def extract_invoice_data_with_pdfplumber(pdf_path):
    """
    Extrae datos de la factura usando pdfplumber (local)
    """
    if not os.path.exists(pdf_path):
        print(f"Error: No se encuentra el archivo {pdf_path}")
        return None

    print(f"Procesando archivo: {pdf_path}")
    print("="*80)

    try:
        text_content = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # Usamos extract_text() simple para obtener el flujo de texto
                # layout=True puede ser útil para tablas, pero para regex simple a veces confunde
                page_text = page.extract_text()
                if page_text:
                    text_content += page_text + "\n"
        
        # Debug: imprimir primeros caracteres
        # print(f"Texto extraído (primeros 500 caracteres):\n{text_content[:500]}\n")

        # 1. Agencia de Carga
        agencia_match = re.search(r'VIC VALCARGO INTERNACIONAL SAS', text_content, re.IGNORECASE)
        agencia_carga_name = agencia_match.group(0) if agencia_match else "No encontrado"
        print(f"Agencia de Carga: {agencia_carga_name}")

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
        
        print(f"Número de Factura: {numero_factura}")

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
        
        print(f"AWBs encontrados: {pedidos_matches}")
        print(f"Total de AWBs: {len(pedidos_matches)}")

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
        
        # Patrón 3: Suma de items si no encuentra total explícito (fallback)
        # Esto es más complejo, por ahora reportamos si no se encuentra
        if valor_gastos_carga is None:
            valor_gastos_carga = "No encontrado"

        print(f"Valor Gastos Carga: {valor_gastos_carga}")
        
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
        print(f"\nError al procesar documento: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Archivos de prueba
    files = ["VVL 15013.pdf", "VVL 12159 v2.pdf"]
    
    output_file = "results.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("Iniciando pruebas con pdfplumber...\n\n")
        
        for pdf_path in files:
            if os.path.exists(pdf_path):
                result = extract_invoice_data_with_pdfplumber(pdf_path)
                
                f.write(f"Procesando archivo: {pdf_path}\n")
                f.write("="*80 + "\n")
                if result:
                    f.write(f"Agencia de Carga: {result['extracted']['agencia_carga']}\n")
                    f.write(f"Número de Factura: {result['extracted']['numero_factura']}\n")
                    f.write(f"AWBs encontrados: {result['extracted']['awbs']}\n")
                    f.write(f"Total de AWBs: {len(result['extracted']['awbs'])}\n")
                    f.write(f"Valor Gastos Carga: {result['extracted']['valor_gastos_carga']}\n")
                else:
                    f.write("Error al extraer datos.\n")
                f.write("\n" + "="*80 + "\n\n")
            else:
                f.write(f"Archivo no encontrado para prueba: {pdf_path}\n")

