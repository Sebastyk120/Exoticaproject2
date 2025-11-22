import pdfplumber
import re
import os
from decimal import Decimal

class AduanaPdfParser:
    """
    Parser for Customs (Aduana) PDF Invoices.
    Supports multiple formats (Format 1 and Format 2).
    """

    @staticmethod
    def parse_amount(amount_str):
        """Converts a Spanish formatted number string (1.234,56) to Decimal."""
        if not amount_str:
            return Decimal('0.00')
        # Remove thousands separator (.) and replace decimal separator (,) with .
        clean_str = amount_str.replace('.', '').replace(',', '.')
        try:
            return Decimal(clean_str)
        except:
            return Decimal('0.00')

    @staticmethod
    def format_awb(awb_raw):
        """Formats AWB as XXX-XXXXXXXX"""
        if len(awb_raw) == 11:
            return f"{awb_raw[:3]}-{awb_raw[3:]}"
        return awb_raw

    def extract_data(self, pdf_path):
        """
        Extracts data from the PDF file.
        Returns a dictionary with the extracted fields.
        """
        if not os.path.exists(pdf_path):
            return {"error": f"File not found: {pdf_path}"}

        data = {
            "filename": os.path.basename(pdf_path),
            "agencia_aduana": "No encontrado",
            "numero_factura": "No encontrado",
            "awbs": [],
            "valor_gastos_aduana": Decimal('0.00'),
            "iva_importacion": Decimal('0.00'),
            "iva_sobre_base": Decimal('0.00')
        }

        try:
            with pdfplumber.open(pdf_path) as pdf:
                full_text = ""
                for page in pdf.pages:
                    # layout=True preserves the visual structure, useful for tables
                    full_text += page.extract_text(layout=True) + "\n"

                # 1. Agencia de Aduana
                if "Arola Aduanas y Consignaciones" in full_text:
                    data["agencia_aduana"] = "Arola Aduanas y Consignaciones, S.L."

                # 2. Número de Factura
                # Pattern: 25-FV-XXXXXX
                inv_match = re.search(r'(\d{2}-FV-\d{6})', full_text)
                if inv_match:
                    data["numero_factura"] = inv_match.group(1)

                # 3. AWBs
                # Pattern: 729 followed by 8 digits (11 digits total)
                # We use lookarounds to ensure we match the full number
                awb_matches = re.findall(r'(?<!\d)(729\d{8})(?!\d)', full_text)
                unique_awbs = sorted(list(set(awb_matches)))
                data["awbs"] = [self.format_awb(awb) for awb in unique_awbs]

                # 4. IVA Importación
                # Pattern: 54IVA (Importación) ... value
                # We find all occurrences and sum them up to get the total expense.
                iva_imp_matches = re.findall(r'54IVA\s*\(Importaci[óo]n\).*?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text, re.IGNORECASE)
                
                total_iva_imp = Decimal('0.00')
                for val in iva_imp_matches:
                    total_iva_imp += self.parse_amount(val)
                data["iva_importacion"] = total_iva_imp

                # 5. Total Gastos Aduana (Total Factura)
                # Format 2 explicit: Total Factura (EUR) 1.289,94
                total_match_f2 = re.search(r'Total\s+Factura\s*\(EUR\)\s*(\d{1,3}(?:\.\d{3})*,\d{2})', full_text, re.IGNORECASE)
                
                if total_match_f2:
                    data["valor_gastos_aduana"] = self.parse_amount(total_match_f2.group(1))
                else:
                    # Format 1: Look for the line starting with EUR (Currency) in the summary
                    # EUR 1.041,13 403,24 637,89 21 133,96 1.175,09
                    eur_line_match = re.search(r'EUR\s+.*?\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s*$', full_text, re.MULTILINE)
                    if eur_line_match:
                        data["valor_gastos_aduana"] = self.parse_amount(eur_line_match.group(1))

                # 6. IVA Sobre Base
                # Format 2: IVA 21% sobre Base 151,86
                iva_base_match_f2 = re.search(r'IVA\s+21%\s+sobre\s+Base\s+(\d{1,3}(?:\.\d{3})*,\d{2})', full_text, re.IGNORECASE)
                if iva_base_match_f2:
                    data["iva_sobre_base"] = self.parse_amount(iva_base_match_f2.group(1))
                else:
                    # Format 1: Look for summary table row starting with IVA21
                    # IVA21 637,89 21 133,96 771,85
                    # We want the 3rd number (133,96)
                    iva_row_match = re.search(r'IVA21\s+[\d.,]+\s+21\s+(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
                    if iva_row_match:
                        data["iva_sobre_base"] = self.parse_amount(iva_row_match.group(1))

        except Exception as e:
            data["error"] = str(e)

        return data

if __name__ == "__main__":
    # Example usage
    parser = AduanaPdfParser()
    files = [
        "25-FV-001455.pdf",
        "25-FV-004677.pdf",
        "25-FV-017518.pdf",
        "25-FV-036056.pdf",
        "25-FV-046908.pdf",
        "25-FV-048873.pdf",
        "25-FV-050753.pdf",
        "25-FV-050955.pdf",
        "25-FV-056617.pdf"
    ]

    print(f"{'File':<20} | {'Factura':<15} | {'AWB':<15} | {'Gastos':<10} | {'IVA Imp':<10} | {'IVA Base':<10}")
    print("-" * 95)

    for f in files:
        res = parser.extract_data(f)
        if "error" in res:
            print(f"{f:<20} | Error: {res['error']}")
            continue
            
        awbs = ",".join(res['awbs'])
        print(f"{res['filename']:<20} | {res['numero_factura']:<15} | {awbs:<15} | {res['valor_gastos_aduana']:<10} | {res['iva_importacion']:<10} | {res['iva_sobre_base']:<10}")
