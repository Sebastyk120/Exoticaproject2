from django.shortcuts import render
from django.db.models import Sum, F, DecimalField, Value, Q, Case, When, ExpressionWrapper
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.http import JsonResponse
from importacion.models import Pedido, DetallePedido, GastosAduana, GastosCarga
from comercial.models import Venta, DetalleVenta
from productos.models import Presentacion, Fruta
from datetime import datetime
from django.http import HttpResponse
import xlsxwriter
from io import BytesIO

def calcular_ventas_netas_por_producto_semana(anio=None, semana=None):
    """
    Calcula las ventas netas por producto y semana.
    Ventas Netas = (valor_x_producto - valor_abono_euro) de DetalleVenta
    """
    # Filtrar por año si se proporciona
    ventas_query = Venta.objects.all()
    if anio:
        ventas_query = ventas_query.filter(fecha_entrega__year=anio)
    
    # Filtrar por semana si se proporciona
    if semana:
        # Modificar para buscar con el patrón "semana-año"
        patron_semana = f"{semana}-{anio}" if anio else f"{semana}-"
        ventas_query = ventas_query.filter(semana__startswith=patron_semana)
    
    # Agrupar las ventas por producto y semana
    ventas_netas = DetalleVenta.objects.filter(
        venta__in=ventas_query
    ).values(
        'presentacion__fruta__nombre',
        'venta__semana'
    ).annotate(
        ventas_netas=Sum(F('valor_x_producto') - 
            Coalesce(
                ExpressionWrapper(
                    F('valor_abono_euro') / Value(Decimal('1.04')),
                    output_field=DecimalField()
                ),
                Value(0, output_field=DecimalField())
            )
        )
    )
    
    # Convertir a un diccionario para fácil acceso
    resultado = {}
    for venta in ventas_netas:
        producto = venta['presentacion__fruta__nombre']
        semana = venta['venta__semana']
        valor = float(venta['ventas_netas'])
        
        if producto not in resultado:
            resultado[producto] = {}
        
        resultado[producto][semana] = valor
    
    return resultado

def calcular_costos_compra_por_producto_semana(anio=None, semana=None):
    """
    Calcula los costos de compra por producto y semana.
    Costos de Compra = valor_x_producto_eur de DetallePedido (ya ajustado por NC)
    """
    # Filtrar por año si se proporciona
    pedidos_query = Pedido.objects.all()
    if anio:
        pedidos_query = pedidos_query.filter(fecha_entrega__year=anio)
    
    # Filtrar por semana si se proporciona
    if semana:
        # Modificar para buscar con el patrón "semana-año"
        patron_semana = f"{semana}-{anio}" if anio else f"{semana}-"
        pedidos_query = pedidos_query.filter(semana__startswith=patron_semana)
    
    # Agrupar los costos por producto y semana
    costos_compra = DetallePedido.objects.filter(
        pedido__in=pedidos_query,
        pedido__pagado=True  # Solo consideramos pedidos pagados que tienen valor_x_producto_eur calculado
    ).values(
        'presentacion__fruta__nombre',
        'pedido__semana'
    ).annotate(
        costo_compra=Sum('valor_x_producto_eur')
    )
    
    # Convertir a un diccionario para fácil acceso
    resultado = {}
    for costo in costos_compra:
        producto = costo['presentacion__fruta__nombre']
        semana = costo['pedido__semana']
        valor = float(costo['costo_compra'])
        
        if producto not in resultado:
            resultado[producto] = {}
        
        resultado[producto][semana] = valor
    
    return resultado

def calcular_gastos_aduana_por_producto_semana(anio=None, semana=None):
    """
    Distribuye los gastos de aduana proporcionalmente a las cajas recibidas y kilos de cada producto.
    """
    # Filtrar por año si se proporciona
    if anio:
        pedidos_año = Pedido.objects.filter(fecha_entrega__year=anio)
    else:
        pedidos_año = Pedido.objects.all()
    
    # Filtrar por semana si se proporciona
    if semana:
        # Modificar para buscar con el patrón "semana-año"
        patron_semana = f"{semana}-{anio}" if anio else f"{semana}-"
        pedidos_año = pedidos_año.filter(semana__startswith=patron_semana)
    
    resultado = {}
    
    # Para cada gasto de aduana
    for gasto_aduana in GastosAduana.objects.all():
        # Obtener los pedidos asociados a este gasto que también estén en el año filtrado
        pedidos = gasto_aduana.pedidos.filter(id__in=pedidos_año)
        
        if not pedidos:
            continue
        
        # Calcular el gasto neto de aduana
        gasto_neto = gasto_aduana.valor_gastos_aduana
        if gasto_aduana.valor_nota_credito:
            gasto_neto -= gasto_aduana.valor_nota_credito
            
        # Si el gasto neto es cero o negativo, continuamos con el siguiente gasto
        if gasto_neto <= 0:
            continue
            
        # Obtener todos los detalles de los pedidos asociados
        detalles_pedidos = DetallePedido.objects.filter(pedido__in=pedidos, pedido__pagado=True)
        
        # Calcular el total de kilos para distribuir proporcionalmente
        total_kilos = detalles_pedidos.aggregate(
            total=Coalesce(Sum('kilos'), Decimal('0'))
        )['total']
        
        # Si no hay kilos registrados, continuamos con el siguiente gasto
        if total_kilos == 0:
            continue
        
        # Distribuir el gasto proporcionalmente por cada detalle
        for detalle in detalles_pedidos:
            producto = detalle.presentacion.fruta.nombre
            semana = detalle.pedido.semana
            
            # Calcular la proporción para este producto basada en kilos
            proporcion = Decimal(detalle.kilos) / total_kilos
            gasto_producto = float(proporcion * gasto_neto)
            
            # Agregar al diccionario de resultado
            if producto not in resultado:
                resultado[producto] = {}
                
            if semana in resultado[producto]:
                resultado[producto][semana] += gasto_producto
            else:
                resultado[producto][semana] = gasto_producto
    
    return resultado

def calcular_gastos_carga_por_producto_semana(anio=None, semana=None):
    """
    Distribuye los gastos de carga proporcionalmente a las cajas recibidas y kilos de cada producto.
    """
    # Filtrar por año si se proporciona
    if anio:
        pedidos_año = Pedido.objects.filter(fecha_entrega__year=anio)
    else:
        pedidos_año = Pedido.objects.all()
    
    # Filtrar por semana si se proporciona
    if semana:
        # Modificar para buscar con el patrón "semana-año"
        patron_semana = f"{semana}-{anio}" if anio else f"{semana}-"
        pedidos_año = pedidos_año.filter(semana__startswith=patron_semana)
    
    resultado = {}
    
    # Para cada gasto de carga
    for gasto_carga in GastosCarga.objects.all():
        # Obtener los pedidos asociados a este gasto que también estén en el año filtrado
        pedidos = gasto_carga.pedidos.filter(id__in=pedidos_año)
        
        if not pedidos:
            continue
        
        # El valor de gasto_carga.valor_gastos_carga_eur ya incluye el ajuste por NC
        gasto_neto = gasto_carga.valor_gastos_carga_eur
            
        # Si el gasto neto es cero o negativo, continuamos con el siguiente gasto
        if gasto_neto <= 0:
            continue
            
        # Obtener todos los detalles de los pedidos asociados
        detalles_pedidos = DetallePedido.objects.filter(pedido__in=pedidos, pedido__pagado=True)
        
        # Calcular el total de kilos para distribuir proporcionalmente
        total_kilos = detalles_pedidos.aggregate(
            total=Coalesce(Sum('kilos'), Decimal('0'))
        )['total']
        
        # Si no hay kilos registrados, continuamos con el siguiente gasto
        if total_kilos == 0:
            continue
        
        # Distribuir el gasto proporcionalmente por cada detalle
        for detalle in detalles_pedidos:
            producto = detalle.presentacion.fruta.nombre
            semana = detalle.pedido.semana
            
            # Calcular la proporción para este producto basada en kilos
            proporcion = Decimal(detalle.kilos) / total_kilos
            gasto_producto = float(proporcion * gasto_neto)
            
            # Agregar al diccionario de resultado
            if producto not in resultado:
                resultado[producto] = {}
                
            if semana in resultado[producto]:
                resultado[producto][semana] += gasto_producto
            else:
                resultado[producto][semana] = gasto_producto
    
    return resultado

def calcular_utilidad_por_producto_semana(anio=None, semana=None):
    """
    Calcula la utilidad por producto y semana según la fórmula:
    Utilidad = (Ventas Netas) - (Costos de Compra + Gastos de Aduana + Gastos de Carga)
    """
    # Obtener todos los componentes
    ventas_netas = calcular_ventas_netas_por_producto_semana(anio, semana)
    costos_compra = calcular_costos_compra_por_producto_semana(anio, semana)
    gastos_aduana = calcular_gastos_aduana_por_producto_semana(anio, semana)
    gastos_carga = calcular_gastos_carga_por_producto_semana(anio, semana)
    
    # Obtener todos los productos y semanas únicos
    productos = set()
    semanas = set()
    
    for diccionario in [ventas_netas, costos_compra, gastos_aduana, gastos_carga]:
        for producto in diccionario:
            productos.add(producto)
            for semana in diccionario[producto]:
                semanas.add(semana)
    
    # Calcular la utilidad para cada combinación de producto y semana
    resultado = {}
    
    for producto in productos:
        resultado[producto] = {}
        
        for semana in semanas:
            # Obtener los componentes o usar 0 si no existen
            venta = ventas_netas.get(producto, {}).get(semana, 0)
            compra = costos_compra.get(producto, {}).get(semana, 0)
            aduana = gastos_aduana.get(producto, {}).get(semana, 0)
            carga = gastos_carga.get(producto, {}).get(semana, 0)
            
            # Calcular utilidad
            utilidad = venta - (compra + aduana + carga)
            
            # Solo agregar si hay alguna transacción para esta combinación
            if venta > 0 or compra > 0 or aduana > 0 or carga > 0:
                resultado[producto][semana] = utilidad
    
    return resultado

def calcular_resumen_utilidad(anio=None, semana=None):
    """
    Calcula un resumen de utilidades totalizando los datos por producto.
    """
    # Obtener datos por producto y semana
    ventas_netas = calcular_ventas_netas_por_producto_semana(anio, semana)
    costos_compra = calcular_costos_compra_por_producto_semana(anio, semana)
    gastos_aduana = calcular_gastos_aduana_por_producto_semana(anio, semana)
    gastos_carga = calcular_gastos_carga_por_producto_semana(anio, semana)
    
    # Obtener todos los productos únicos
    productos = set()
    for diccionario in [ventas_netas, costos_compra, gastos_aduana, gastos_carga]:
        for producto in diccionario:
            productos.add(producto)
    
    # Calcular totales por producto
    resultado = []
    
    for producto in productos:
        # Sumar todas las semanas para cada componente
        total_ventas = sum(ventas_netas.get(producto, {}).values())
        total_compra = sum(costos_compra.get(producto, {}).values())
        total_aduana = sum(gastos_aduana.get(producto, {}).values())
        total_carga = sum(gastos_carga.get(producto, {}).values())
        
        # Calcular utilidad y margen
        total_costos = total_compra + total_aduana + total_carga
        utilidad = total_ventas - total_costos
        margen = (utilidad / total_ventas * 100) if total_ventas > 0 else 0
        
        # Agregar al resultado
        resultado.append({
            'producto': producto,
            'ventas_netas': round(total_ventas, 2),
            'costo_compra': round(total_compra, 2),
            'gastos_aduana': round(total_aduana, 2),
            'gastos_carga': round(total_carga, 2),
            'utilidad': round(utilidad, 2),
            'margen': round(margen, 2),
            'total_costos': round(total_costos, 2)
        })
    
    # Ordenar por utilidad descendente
    resultado.sort(key=lambda x: x['utilidad'], reverse=True)
    
    return resultado

def calcular_totales_globales(anio=None, semana=None):
    """
    Calcula los totales globales para mostrar en las tarjetas resumen.
    """
    # Usar el resumen de utilidad para obtener los totales
    resumen = calcular_resumen_utilidad(anio, semana)
    
    if not resumen:
        return {
            'utilidad_total': 0,
            'ventas_netas': 0,
            'costo_total': 0,
            'margen_promedio': 0
        }
    
    # Calcular los totales
    utilidad_total = sum(item['utilidad'] for item in resumen)
    ventas_netas = sum(item['ventas_netas'] for item in resumen)
    costo_total = sum(item['total_costos'] for item in resumen)
    
    # Calcular el margen promedio ponderado
    if ventas_netas > 0:
        margen_promedio = (utilidad_total / ventas_netas) * 100
    else:
        margen_promedio = 0
    
    return {
        'utilidad_total': round(utilidad_total, 2),
        'ventas_netas': round(ventas_netas, 2),
        'costo_total': round(costo_total, 2),
        'margen_promedio': round(margen_promedio, 2)
    }

# Función auxiliar para procesar el parámetro de semana
def procesar_parametro_semana(semana_str):
    """
    Procesa el parámetro de semana del request y devuelve el número de semana.
    El formato esperado puede ser "13" o "13-2025".
    """
    if not semana_str:
        return None
    
    # Si el formato es "13-2025", extraer sólo el número de semana
    if '-' in semana_str:
        try:
            semana_num = int(semana_str.split('-')[0])
            return semana_num
        except (ValueError, IndexError):
            return None
    
    # Si el formato es sólo un número
    try:
        return int(semana_str)
    except ValueError:
        return None

def dashboard_utilidades(request):
    """
    Vista principal para el dashboard de utilidades.
    """
    # Obtener el año y semana seleccionados o usar valores por defecto
    anio = request.GET.get('anio', datetime.now().year)
    semana_str = request.GET.get('semana')
    
    try:
        anio = int(anio)
    except ValueError:
        anio = datetime.now().year
    
    # Usar la nueva función para procesar la semana
    semana = procesar_parametro_semana(semana_str)
    
    # Calcular los datos para las tarjetas de resumen
    totales = calcular_totales_globales(anio, semana)
    
    # Obtener el resumen de utilidad por producto
    resumen_utilidad = calcular_resumen_utilidad(anio, semana)
    
    return render(request, 'dashboard/utilidades.html', {
        'anio': anio,
        'semana': semana,
        'totales': totales,
        'resumen_utilidad': resumen_utilidad
    })

# API endpoints para los datos del dashboard

def api_semanas_disponibles(request):
    """API para obtener las semanas que tienen datos en el año seleccionado."""
    anio = request.GET.get('anio')
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = None
    
    # Obtener semanas únicas de Ventas y Pedidos
    semanas_venta = set(Venta.objects.filter(
        fecha_entrega__year=anio
    ).values_list('semana', flat=True).distinct())
    
    semanas_pedido = set(Pedido.objects.filter(
        fecha_entrega__year=anio
    ).values_list('semana', flat=True).distinct())
    
    # Combinar y ordenar las semanas
    semanas = sorted(list(semanas_venta.union(semanas_pedido)))
    
    return JsonResponse({'semanas': semanas})

def api_resumen_utilidad(request):
    """API para obtener el resumen de utilidad por producto."""
    anio = request.GET.get('anio')
    semana_str = request.GET.get('semana')
    formato = request.GET.get('format')
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = None
    
    # Usar la nueva función para procesar la semana
    semana = procesar_parametro_semana(semana_str)
    
    resumen = calcular_resumen_utilidad(anio, semana)
    
    # Verificar si se solicitó formato Excel
    if formato == 'xlsx':
        return exportar_resumen_excel(resumen, anio, semana)
    
    return JsonResponse({'data': resumen})

def exportar_resumen_excel(resumen, anio, semana=None):
    """Genera un archivo Excel con el resumen de utilidades."""
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet("Utilidades")
    
    # Formatos
    title_format = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'align': 'center',
        'valign': 'vcenter',
        'bg_color': '#3B82F6',
        'font_color': 'white'
    })
    
    header_format = workbook.add_format({
        'bold': True,
        'font_size': 11,
        'align': 'center',
        'valign': 'vcenter',
        'bg_color': '#D1D5DB',
        'border': 1
    })
    
    money_format = workbook.add_format({
        'num_format': '€#,##0.00',
        'align': 'right',
        'border': 1
    })
    
    percent_format = workbook.add_format({
        'num_format': '0.00%',
        'align': 'right',
        'border': 1
    })
    
    text_format = workbook.add_format({
        'align': 'left',
        'border': 1
    })
    
    # Título
    titulo = f"Dashboard de Utilidades por Producto - Año {anio if anio else 'Todos'}"
    if semana:
        titulo += f" - Semana {semana}"
        
    worksheet.merge_range('A1:H1', titulo, title_format)
    worksheet.set_row(0, 30)
    
    # Encabezados
    headers = [
        'Producto', 'Ventas Netas', 'Costo Compra', 'Gastos Aduana', 
        'Gastos Carga', 'Utilidad', 'Margen', 'Costos Totales'
    ]
    
    for col, header in enumerate(headers):
        worksheet.write(2, col, header, header_format)
    
    # Datos
    for row, item in enumerate(resumen):
        worksheet.write(row + 3, 0, item['producto'], text_format)
        worksheet.write(row + 3, 1, item['ventas_netas'], money_format)
        worksheet.write(row + 3, 2, item['costo_compra'], money_format)
        worksheet.write(row + 3, 3, item['gastos_aduana'], money_format)
        worksheet.write(row + 3, 4, item['gastos_carga'], money_format)
        worksheet.write(row + 3, 5, item['utilidad'], money_format)
        worksheet.write(row + 3, 6, item['margen'] / 100, percent_format)
        worksheet.write(row + 3, 7, item['total_costos'], money_format)
    
    # Ajustar anchos de columna
    worksheet.set_column('A:A', 25)
    worksheet.set_column('B:H', 15)
    
    # Calcular totales
    totales = calcular_totales_globales(anio, semana)
    
    # Agregar totales al final
    total_row = len(resumen) + 4
    worksheet.write(total_row, 0, 'TOTALES', header_format)
    worksheet.write(total_row, 1, totales['ventas_netas'], money_format)
    worksheet.write(total_row, 5, totales['utilidad_total'], money_format)
    worksheet.write(total_row, 6, totales['margen_promedio'] / 100, percent_format)
    worksheet.write(total_row, 7, totales['costo_total'], money_format)
    
    workbook.close()
    output.seek(0)
    
    filename_parts = ['utilidades']
    if anio:
        filename_parts.append(str(anio))
    if semana:
        filename_parts.append(f"semana_{semana}")
    
    filename = "_".join(filename_parts) + ".xlsx"
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response

def api_utilidad_por_semana(request):
    """API para obtener la utilidad por producto y semana."""
    anio = request.GET.get('anio')
    semana_str = request.GET.get('semana')
    producto = request.GET.get('producto')
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = None
    
    # Usar la nueva función para procesar la semana
    semana = procesar_parametro_semana(semana_str)
    
    # Calcular la utilidad por producto y semana
    utilidad_semana = calcular_utilidad_por_producto_semana(anio, semana)
    
    # Si se especifica un producto, filtrar solo ese producto
    if producto and producto != 'todos':
        if producto in utilidad_semana:
            resultado = {producto: utilidad_semana[producto]}
        else:
            # Si el producto no existe en los datos, retornar vacío
            resultado = {}
    else:
        resultado = utilidad_semana
    
    # Preparar los datos por semana para Chart.js
    semanas = sorted(set(semana for prod_data in resultado.values() for semana in prod_data))
    datasets = []
    
    for prod, data in resultado.items():
        dataset = {
            'label': prod,
            'data': [data.get(semana, 0) for semana in semanas]
        }
        datasets.append(dataset)
    
    return JsonResponse({
        'labels': semanas,
        'datasets': datasets
    })

def api_distribucion_costos(request):
    """API para obtener la distribución de costos por tipo."""
    anio = request.GET.get('anio')
    semana_str = request.GET.get('semana')
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = None
    
    # Usar la nueva función para procesar la semana
    semana = procesar_parametro_semana(semana_str)
    
    # Obtener el resumen de costos del cálculo de utilidad
    resumen = calcular_resumen_utilidad(anio, semana)
    
    # Calcular los totales por tipo de costo
    total_compra = sum(item['costo_compra'] for item in resumen)
    total_aduana = sum(item['gastos_aduana'] for item in resumen)
    total_carga = sum(item['gastos_carga'] for item in resumen)
    
    return JsonResponse({
        'labels': ['Compra', 'Aduana', 'Carga'],
        'data': [round(total_compra, 2), round(total_aduana, 2), round(total_carga, 2)]
    })

def api_margen_por_producto(request):
    """API para obtener el margen por producto."""
    anio = request.GET.get('anio')
    semana_str = request.GET.get('semana')
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = None
    
    # Usar la nueva función para procesar la semana
    semana = procesar_parametro_semana(semana_str)
    
    # Obtener el resumen de utilidad por producto
    resumen = calcular_resumen_utilidad(anio, semana)
    
    # Extraer los datos para el gráfico
    productos = [item['producto'] for item in resumen]
    margenes = [item['margen'] for item in resumen]
    
    return JsonResponse({
        'labels': productos,
        'data': margenes
    })

def api_productos_rentables(request):
    """API para obtener los productos más rentables."""
    anio = request.GET.get('anio')
    semana_str = request.GET.get('semana')
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = None
    
    # Usar la nueva función para procesar la semana
    semana = procesar_parametro_semana(semana_str)
    
    # Obtener el resumen de utilidad por producto
    resumen = calcular_resumen_utilidad(anio, semana)
    
    # Ordenar por utilidad y tomar los 5 más rentables
    top_productos = sorted(resumen, key=lambda x: x['utilidad'], reverse=True)[:5]
    
    # Extraer los datos para el gráfico
    productos = [item['producto'] for item in top_productos]
    utilidades = [item['utilidad'] for item in top_productos]
    
    return JsonResponse({
        'labels': productos,
        'data': utilidades
    })

def api_totales_globales(request):
    """API para obtener los totales globales."""
    anio = request.GET.get('anio')
    semana_str = request.GET.get('semana')
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = None
    
    # Usar la nueva función para procesar la semana
    semana = procesar_parametro_semana(semana_str)
    
    # Calcular los totales globales
    totales = calcular_totales_globales(anio, semana)
    
    return JsonResponse(totales)
