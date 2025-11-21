# Implementación de Google Document AI para Extracción de Facturas

## Cambios Realizados

### 1. Dependencias Actualizadas
Se agregó la librería de Google Document AI al archivo `requirements.txt`:
```
google-cloud-documentai==2.82.0
```

### 2. Modificación de `importacion/views_carga.py`

#### Nuevas Importaciones
```python
import os
from google.cloud import documentai_v1
from google.api_core.client_options import ClientOptions
```

#### Nueva Función: `extract_invoice_data_with_docai()`
Esta función reemplaza la extracción manual con `pdfminer` por Google Document AI:
- Utiliza las credenciales de GCP desde variables de entorno
- Procesa el PDF con el Invoice Processor de Document AI
- Extrae entidades estructuradas del documento
- Retorna texto completo y entidades identificadas

#### Función Modificada: `process_pdf()`
La función ahora:
1. Llama a `extract_invoice_data_with_docai()` para procesar el PDF
2. Extrae los siguientes campos usando las entidades de Document AI:
   - **agencia_carga**: De la entidad `supplier_name` o búsqueda en texto
   - **numero_factura**: De la entidad `invoice_id` o patrón "VVL XXXXX"
   - **AWB (pedidos)**: Búsqueda de patrones XXX-XXXXXXXX en el texto
   - **valor_gastos_carga**: De las entidades `total_amount` o `net_amount`

## Variables de Entorno Requeridas

Las siguientes variables ya están configuradas en tu archivo `.env`:
```
GCP_PROJECT_ID=1066666643132
GCP_LOCATION=eu
GCP_INVOICE_PROCESSOR_ID=a3cfc06490d9bba7
GOOGLE_APPLICATION_CREDENTIALS=C:\Users\Sebastian\Downloads\perfect-purpose-478621-a8-0d50ec2310bc.json
```

## Instalación

1. Instalar las nuevas dependencias:
```bash
pip install -r requirements.txt
```

2. Verificar que el archivo de credenciales de Google Cloud existe en la ruta especificada en `GOOGLE_APPLICATION_CREDENTIALS`

## Pruebas

### Datos de Ejemplo (Factura VVL 15013)
Según el PDF de ejemplo, los valores esperados son:
- **numero_factura**: 15013
- **agencia_carga**: VIC VALCARGO INTERNACIONAL SAS
- **Pedido.awb**: 729-45608824
- **valor_gastos_carga**: 2408.84 (formato: 2.408,84 en el PDF)

### Cómo Probar
1. Acceder a la vista de carga de facturas
2. Subir el archivo `VVL 15013.pdf`
3. Verificar en los logs que se extraen correctamente:
   - Las entidades de Document AI
   - El número de factura
   - Los AWBs
   - El valor total

### Logs de Depuración
La función incluye logs detallados:
```python
logger.info(f"Texto extraído: {text[:500]}...")
logger.info(f"Entidades extraídas: {entities}")
logger.info(f"AWBs encontrados: {pedidos_matches}")
logger.info(f"Valor gastos carga: {valor_gastos_carga}")
```

## Ventajas de Document AI

1. **Mayor Precisión**: Document AI está entrenado específicamente para facturas
2. **Extracción Estructurada**: Identifica automáticamente campos como proveedor, total, fecha, etc.
3. **Manejo de Formatos**: Funciona con diferentes layouts de facturas
4. **Menos Mantenimiento**: No requiere actualizar expresiones regulares cuando cambia el formato

## Próximos Pasos

1. Probar con el PDF de ejemplo
2. Ajustar los patrones de extracción según los resultados
3. Considerar agregar más campos de las entidades de Document AI si es necesario
4. Implementar manejo de errores más robusto

## Notas Importantes

- Document AI puede identificar más entidades de las que estamos usando actualmente
- Los nombres de las entidades pueden variar según el procesador (invoice_id, supplier_name, total_amount, etc.)
- Si Document AI no encuentra una entidad, el código hace fallback a búsqueda por regex en el texto

