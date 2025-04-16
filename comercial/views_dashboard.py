from django.shortcuts import render
from django.db.models import Sum, F, DecimalField, Value, Q, Case, When, ExpressionWrapper
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from importacion.models import Pedido, DetallePedido, GastosAduana, GastosCarga
from comercial.models import Venta, DetalleVenta
from productos.models import Presentacion, Fruta
from datetime import datetime
import xlsxwriter
from io import BytesIO

def calcular_ventas_netas_por_producto_semana(anio=None, semana=None, trimestre=None):
    """
    Calcula las ventas netas por producto y semana/trimestre.
    Ventas Netas = (valor_x_producto - valor_abono_euro_sin_iva) de DetalleVenta
    Se asegura que ambos valores estén en la misma base (netos, sin IVA).
    """
    ventas_query = Venta.objects.all()
    if semana:
        ventas_query = ventas_query.filter(semana=semana)
    elif trimestre:
        ventas_query = filtrar_por_trimestre(ventas_query, anio, trimestre)
    elif anio:
        ventas_query = ventas_query.filter(fecha_entrega__year=anio)

    # Agrupar las ventas por producto y semana
    ventas_netas = DetalleVenta.objects.filter(
        venta__in=ventas_query
    ).values(
        'presentacion__fruta__nombre',
        'venta__semana',
        'venta__porcentaje_iva'
    ).annotate(
        # Restar el abono neto (sin IVA) del valor_x_producto
        ventas_netas=Sum(
            ExpressionWrapper(
                F('valor_x_producto') - 
                Case(
                    When(
                        valor_abono_euro__gt=0,
                        then=F('valor_abono_euro') / (1 + F('venta__porcentaje_iva') / 100)
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                ),
                output_field=DecimalField()
            )
        )
    )

    resultado = {}
    for venta in ventas_netas:
        producto = venta['presentacion__fruta__nombre']
        semana = venta['venta__semana']
        # Mantener como Decimal hasta el final
        valor = venta['ventas_netas'] if venta['ventas_netas'] is not None else Decimal('0')
        if producto not in resultado:
            resultado[producto] = {}
        resultado[producto][semana] = float(valor)
    return resultado

def calcular_costos_compra_por_producto_semana(anio=None, semana=None, trimestre=None):
    """
    Calcula los costos de compra por producto y semana/trimestre.
    Costos de Compra = valor_x_producto_eur de DetallePedido (ya ajustado por NC)
    Actualizada para usar el formato completo de semana.
    """
    pedidos_query = Pedido.objects.all()
    if semana:
        pedidos_query = pedidos_query.filter(semana=semana)
    elif trimestre:
        pedidos_query = filtrar_por_trimestre(pedidos_query, anio, trimestre)
    elif anio:
        pedidos_query = pedidos_query.filter(fecha_entrega__year=anio)
    
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

def calcular_gastos_aduana_por_producto_semana(anio=None, semana=None, trimestre=None):
    """
    Distribuye los gastos de aduana proporcionalmente a las cajas recibidas y kilos de cada producto.
    Actualizada para usar el formato completo de semana.
    """
    if semana:
        pedidos_año = Pedido.objects.filter(semana=semana)
    elif trimestre:
        pedidos_año = filtrar_por_trimestre(Pedido.objects.all(), anio, trimestre)
    elif anio:
        pedidos_año = Pedido.objects.filter(fecha_entrega__year=anio)
    else:
        pedidos_año = Pedido.objects.all()
    
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

def calcular_gastos_carga_por_producto_semana(anio=None, semana=None, trimestre=None):
    """
    Distribuye los gastos de carga proporcionalmente a las cajas recibidas y kilos de cada producto.
    Actualizada para usar el formato completo de semana.
    """
    if semana:
        pedidos_año = Pedido.objects.filter(semana=semana)
    elif trimestre:
        pedidos_año = filtrar_por_trimestre(Pedido.objects.all(), anio, trimestre)
    elif anio:
        pedidos_año = Pedido.objects.filter(fecha_entrega__year=anio)
    else:
        pedidos_año = Pedido.objects.all()
    
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

def calcular_utilidad_por_producto_semana(anio=None, semana=None, trimestre=None):
    """
    Calcula la utilidad por producto y semana/trimestre según la fórmula:
    Utilidad = (Ventas Netas) - (Costos de Compra + Gastos de Aduana + Gastos de Carga)
    """
    # Obtener todos los componentes
    ventas_netas = calcular_ventas_netas_por_producto_semana(anio, semana, trimestre)
    costos_compra = calcular_costos_compra_por_producto_semana(anio, semana, trimestre)
    gastos_aduana = calcular_gastos_aduana_por_producto_semana(anio, semana, trimestre)
    gastos_carga = calcular_gastos_carga_por_producto_semana(anio, semana, trimestre)
    
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

def calcular_abono_por_producto_semana(anio=None, semana=None, trimestre=None):
    """
    Calcula el valor de los abonos por producto y semana/trimestre.
    Devuelve los datos como un diccionario por producto y semana.
    Se asegura de usar Decimal hasta el final.
    """
    ventas_query = Venta.objects.all()
    if semana:
        ventas_query = ventas_query.filter(semana=semana)
    elif trimestre:
        ventas_query = filtrar_por_trimestre(ventas_query, anio, trimestre)
    elif anio:
        ventas_query = ventas_query.filter(fecha_entrega__year=anio)

    abonos = DetalleVenta.objects.filter(
        venta__in=ventas_query,
        valor_abono_euro__gt=0
    ).values(
        'presentacion__fruta__nombre',
        'venta__semana',
        'venta__porcentaje_iva'
    ).annotate(
        valor_abono=Sum(
            ExpressionWrapper(
                F('valor_abono_euro') / (1 + F('venta__porcentaje_iva') / 100),
                output_field=DecimalField()
            )
        )
    )

    resultado = {}
    for abono in abonos:
        producto = abono['presentacion__fruta__nombre']
        semana = abono['venta__semana']
        valor = abono['valor_abono'] if abono['valor_abono'] is not None else Decimal('0')
        if producto not in resultado:
            resultado[producto] = {}
        resultado[producto][semana] = float(valor)
    return resultado

def calcular_resumen_utilidad(anio=None, semana=None, trimestre=None):
    """
    Calcula un resumen de utilidades totalizando los datos por producto.
    """
    # Obtener datos por producto y semana/trimestre
    ventas_netas = calcular_ventas_netas_por_producto_semana(anio, semana, trimestre)
    costos_compra = calcular_costos_compra_por_producto_semana(anio, semana, trimestre)
    gastos_aduana = calcular_gastos_aduana_por_producto_semana(anio, semana, trimestre)
    gastos_carga = calcular_gastos_carga_por_producto_semana(anio, semana, trimestre)
    abonos = calcular_abono_por_producto_semana(anio, semana, trimestre)  # Obtener datos de abono
    
    # Obtener todos los productos únicos
    productos = set()
    for diccionario in [ventas_netas, costos_compra, gastos_aduana, gastos_carga, abonos]:
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
        total_abono = sum(abonos.get(producto, {}).values())  # Sumar abonos
        
        # Calcular utilidad y margen
        total_costos = total_compra + total_aduana + total_carga
        utilidad = total_ventas - total_costos
        margen = (utilidad / total_ventas * 100) if total_ventas > 0 else 0

        # Solo agregar si hay algún valor distinto de cero
        if any([
            total_ventas != 0,
            total_compra != 0,
            total_aduana != 0,
            total_carga != 0,
            total_abono != 0,
            utilidad != 0
        ]):
            resultado.append({
                'producto': producto,
                'ventas_netas': round(total_ventas, 2),
                'costo_compra': round(total_compra, 2),
                'gastos_aduana': round(total_aduana, 2),
                'gastos_carga': round(total_carga, 2),
                'valor_abono': round(total_abono, 2),  # Nuevo campo de abono
                'utilidad': round(utilidad, 2),
                'margen': round(margen, 2),
                'total_costos': round(total_costos, 2)
            })
    
    # Ordenar por utilidad descendente
    resultado.sort(key=lambda x: x['utilidad'], reverse=True)
    
    return resultado

def calcular_totales_globales(anio=None, semana=None, trimestre=None):
    """
    Calcula los totales globales para mostrar en las tarjetas resumen.
    """
    # Usar el resumen de utilidad para obtener los totales
    resumen = calcular_resumen_utilidad(anio, semana, trimestre)
    
    if not resumen:
        return {
            'utilidad_total': 0,
            'ventas_netas': 0,
            'costo_total': 0,
            'margen_promedio': 0,
            'perdidas_totales': 0,
            'valor_abono_total': 0  # Nuevo campo
        }
    
    # Calcular los totales
    utilidad_total = sum(item['utilidad'] for item in resumen)
    ventas_netas = sum(item['ventas_netas'] for item in resumen)
    costo_total = sum(item['total_costos'] for item in resumen)
    valor_abono_total = sum(item['valor_abono'] for item in resumen)  # Nuevo cálculo
    
    # Calcular total de pérdidas (solo utilidades negativas)
    perdidas_totales = abs(sum(item['utilidad'] for item in resumen if item['utilidad'] < 0))
    
    # Calcular el margen promedio ponderado
    if ventas_netas > 0:
        margen_promedio = (utilidad_total / ventas_netas) * 100
    else:
        margen_promedio = 0
    
    return {
        'utilidad_total': round(utilidad_total, 2),
        'ventas_netas': round(ventas_netas, 2),
        'costo_total': round(costo_total, 2),
        'margen_promedio': round(margen_promedio, 2),
        'perdidas_totales': round(perdidas_totales, 2),
        'valor_abono_total': round(valor_abono_total, 2)  # Nuevo campo
    }

# Función auxiliar para procesar el parámetro de semana - actualizada
def procesar_parametro_semana(semana_str, anio=None):
    """
    Procesa el parámetro de semana del request.
    Ahora simplemente devuelve el valor de semana_str tal cual viene,
    ya que se espera que incluya el año directamente.
    """
    if not semana_str or semana_str == 'cargando' or semana_str == 'todas':
        return None
        
    # Devolver la semana tal cual viene, ya con el formato "semana-año"
    return semana_str

# Función auxiliar para filtrar por trimestre - corregida
def filtrar_por_trimestre(query, anio, trimestre):
    """
    Filtra un queryset por trimestre del año.
    """
    if not trimestre:
        return query
    
    # Si no se proporciona el año, usar el año actual
    if not anio:
        anio = datetime.now().year
    
    try:
        anio = int(anio)
        trimestre = int(trimestre)
        
        # Definir los rangos de meses para cada trimestre
        if trimestre == 1:  # Enero a Marzo
            filtered_query = query.filter(fecha_entrega__year=anio, fecha_entrega__month__range=(1, 3))
        elif trimestre == 2:  # Abril a Junio
            filtered_query = query.filter(fecha_entrega__year=anio, fecha_entrega__month__range=(4, 6))
        elif trimestre == 3:  # Julio a Septiembre
            filtered_query = query.filter(fecha_entrega__year=anio, fecha_entrega__month__range=(7, 9))
        elif trimestre == 4:  # Octubre a Diciembre
            filtered_query = query.filter(fecha_entrega__year=anio, fecha_entrega__month__range=(10, 12))
        else:
            return query
        
        return filtered_query
    except (ValueError, TypeError):
        return query

@login_required
def dashboard_utilidades(request):
    """
    Vista principal para el dashboard de utilidades.
    """
    # Obtener el año, semana y trimestre seleccionados
    anio = request.GET.get('anio', datetime.now().year)
    semana_str = request.GET.get('semana')
    trimestre = request.GET.get('trimestre')
    
    try:
        anio = int(anio)
    except ValueError:
        anio = datetime.now().year
    
    # Usar la función para procesar la semana pasando también el anio
    semana = procesar_parametro_semana(semana_str, anio)
    
    # Calcular los datos para las tarjetas de resumen
    totales = calcular_totales_globales(anio, semana, trimestre)
    
    # Obtener el resumen de utilidad por producto
    resumen_utilidad = calcular_resumen_utilidad(anio, semana, trimestre)
    
    return render(request, 'dashboard/utilidades.html', {
        'anio': anio,
        'semana': semana,
        'trimestre': trimestre,
        'totales': totales,
        'resumen_utilidad': resumen_utilidad
    })

# API endpoints para los datos del dashboard

@login_required
def api_semanas_disponibles(request):
    """API para obtener las semanas que tienen datos en el año seleccionado."""
    anio = request.GET.get('anio')
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = None
    
    # No filtramos por año aquí para obtener todas las semanas de todos los años
    # Esto permite que el selector muestre semanas de diferentes años
    
    # Obtener semanas únicas de Ventas y Pedidos sin filtrar por año
    semanas_venta = set(Venta.objects.values_list('semana', flat=True).distinct())
    semanas_pedido = set(Pedido.objects.filter(semana__isnull=False).values_list('semana', flat=True).distinct())
    
    # Combinar y ordenar las semanas
    semanas = sorted(list(semanas_venta.union(semanas_pedido)))
    
    return JsonResponse({'semanas': semanas})

@login_required
def api_resumen_utilidad(request):
    """API para obtener el resumen de utilidad por producto."""
    anio = request.GET.get('anio')
    semana_str = request.GET.get('semana')
    trimestre = request.GET.get('trimestre')
    formato = request.GET.get('format')
    
    # Ignorar semana="cargando"
    if semana_str == 'cargando':
        semana_str = None
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = datetime.now().year
    
    # Usar la función para procesar la semana pasando también el anio
    semana = procesar_parametro_semana(semana_str, anio)
    
    # Procesar trimestre y asegurar que no se use con semana
    try:
        trimestre = int(trimestre) if trimestre else None
        if trimestre and semana:
            semana = None
    except ValueError:
        trimestre = None
    
    resumen = calcular_resumen_utilidad(anio, semana, trimestre)
    
    # Verificar si se solicitó formato Excel
    if formato == 'xlsx':
        return exportar_resumen_excel(resumen, anio, semana, trimestre)
    
    return JsonResponse({'data': resumen})

def exportar_resumen_excel(resumen, anio, semana=None, trimestre=None):
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
    elif trimestre:
        titulo += f" - Trimestre {trimestre}"
        
    worksheet.merge_range('A1:H1', titulo, title_format)
    worksheet.set_row(0, 30)
    
    # Encabezados - Actualizado para incluir facturas abono
    headers = [
        'Producto', 'Ventas Netas', 'Facturas Abono', 'Costo Compra', 'Gastos Aduana', 
        'Gastos Carga', 'Utilidad', 'Margen', 'Costos Totales'
    ]
    
    for col, header in enumerate(headers):
        worksheet.write(2, col, header, header_format)
    
    # Datos - Actualizado para incluir facturas abono
    for row, item in enumerate(resumen):
        worksheet.write(row + 3, 0, item['producto'], text_format)
        worksheet.write(row + 3, 1, item['ventas_netas'], money_format)
        worksheet.write(row + 3, 2, item['valor_abono'], money_format)  # Nueva columna
        worksheet.write(row + 3, 3, item['costo_compra'], money_format)
        worksheet.write(row + 3, 4, item['gastos_aduana'], money_format)
        worksheet.write(row + 3, 5, item['gastos_carga'], money_format)
        worksheet.write(row + 3, 6, item['utilidad'], money_format)
        worksheet.write(row + 3, 7, item['margen'] / 100, percent_format)
        worksheet.write(row + 3, 8, item['total_costos'], money_format)
    
    # Ajustar anchos de columna
    worksheet.set_column('A:A', 25)
    worksheet.set_column('B:I', 15)  # Actualizado para incluir la nueva columna
    
    # Calcular totales
    totales = calcular_totales_globales(anio, semana, trimestre)
    
    # Agregar totales al final - Actualizado para incluir valor abono
    total_row = len(resumen) + 4
    worksheet.write(total_row, 0, 'TOTALES', header_format)
    worksheet.write(total_row, 1, totales['ventas_netas'], money_format)
    worksheet.write(total_row, 2, totales['valor_abono_total'], money_format)  # Nuevo valor
    worksheet.write(total_row, 5, totales['utilidad_total'], money_format)
    worksheet.write(total_row, 6, totales['margen_promedio'] / 100, percent_format)
    worksheet.write(total_row, 8, totales['costo_total'], money_format)
    
    # Agregar pérdidas totales
    worksheet.write(total_row + 1, 0, 'PÉRDIDAS TOTALES', header_format)
    worksheet.write(total_row + 1, 5, totales['perdidas_totales'], money_format)
    
    workbook.close()
    output.seek(0)
    
    filename_parts = ['utilidades']
    if anio:
        filename_parts.append(str(anio))
    if semana:
        filename_parts.append(f"semana_{semana}")
    elif trimestre:
        filename_parts.append(f"trimestre_{trimestre}")
    
    filename = "_".join(filename_parts) + ".xlsx"
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response

@login_required
def api_utilidad_por_semana(request):
    """API para obtener la utilidad por producto y semana/trimestre."""
    anio = request.GET.get('anio')
    semana_str = request.GET.get('semana')
    trimestre = request.GET.get('trimestre')
    producto = request.GET.get('producto')
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = None
    
    # Usar la función para procesar la semana pasando también el anio
    semana = procesar_parametro_semana(semana_str, anio)
    
    # Procesar trimestre
    try:
        trimestre = int(trimestre) if trimestre else None
    except ValueError:
        trimestre = None
    
    # Calcular la utilidad por producto y periodo
    utilidad_semana = calcular_utilidad_por_producto_semana(anio, semana, trimestre)
    
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

@login_required
def api_distribucion_costos(request):
    """API para obtener la distribución de costos por tipo."""
    anio = request.GET.get('anio')
    semana_str = request.GET.get('semana')
    trimestre = request.GET.get('trimestre')
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = None
    
    # Usar la función para procesar la semana pasando también el anio
    semana = procesar_parametro_semana(semana_str, anio)
    
    # Procesar trimestre
    try:
        trimestre = int(trimestre) if trimestre else None
    except ValueError:
        trimestre = None
    
    # Obtener el resumen de costos del cálculo de utilidad
    resumen = calcular_resumen_utilidad(anio, semana, trimestre)
    
    # Calcular los totales por tipo de costo
    total_compra = sum(item['costo_compra'] for item in resumen)
    total_aduana = sum(item['gastos_aduana'] for item in resumen)
    total_carga = sum(item['gastos_carga'] for item in resumen)
    
    return JsonResponse({
        'labels': ['Compra', 'Aduana', 'Carga'],
        'data': [round(total_compra, 2), round(total_aduana, 2), round(total_carga, 2)]
    })

@login_required
def api_margen_por_producto(request):
    """API para obtener el margen por producto."""
    anio = request.GET.get('anio')
    semana_str = request.GET.get('semana')
    trimestre = request.GET.get('trimestre')
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = None
    
    # Usar la función para procesar la semana pasando también el anio
    semana = procesar_parametro_semana(semana_str, anio)
    
    # Procesar trimestre
    try:
        trimestre = int(trimestre) if trimestre else None
    except ValueError:
        trimestre = None
    
    # Obtener el resumen de utilidad por producto
    resumen = calcular_resumen_utilidad(anio, semana, trimestre)
    
    # Extraer los datos para el gráfico
    productos = [item['producto'] for item in resumen]
    margenes = [item['margen'] for item in resumen]
    
    return JsonResponse({
        'labels': productos,
        'data': margenes
    })

@login_required
def api_productos_rentables(request):
    """API para obtener los productos más rentables."""
    anio = request.GET.get('anio')
    semana_str = request.GET.get('semana')
    trimestre = request.GET.get('trimestre')
    
    try:
        anio = int(anio) if anio else None
    except ValueError:
        anio = None
    
    # Usar la función para procesar la semana pasando también el anio
    semana = procesar_parametro_semana(semana_str, anio)
    
    # Procesar trimestre
    try:
        trimestre = int(trimestre) if trimestre else None
    except ValueError:
        trimestre = None
    
    # Obtener el resumen de utilidad por producto
    resumen = calcular_resumen_utilidad(anio, semana, trimestre)
    
    # Filtrar solo productos con utilidad positiva
    productos_rentables = [item for item in resumen if item['utilidad'] > 0]
    
    # Ordenar por utilidad y tomar los 5 más rentables
    top_productos = sorted(productos_rentables, key=lambda x: x['utilidad'], reverse=True)[:5]
    
    # Extraer los datos para el gráfico
    productos = [item['producto'] for item in top_productos]
    utilidades = [item['utilidad'] for item in top_productos]
    
    return JsonResponse({
        'labels': productos,
        'data': utilidades
    })

@login_required
def api_totales_globales(request):
    """API para obtener los totales globales."""
    anio = request.GET.get('anio')
    semana_str = request.GET.get('semana')
    trimestre = request.GET.get('trimestre')
    
    # Ignorar semana="cargando"
    if semana_str == 'cargando':
        semana_str = None
    
    try:
        anio = int(anio) if anio else datetime.now().year
    except ValueError:
        anio = datetime.now().year
    
    # Usar la función para procesar la semana pasando también el anio
    semana = procesar_parametro_semana(semana_str, anio)
    
    # Procesar trimestre
    try:
        trimestre = int(trimestre) if trimestre else None
        if trimestre and semana:
            # Priorizar trimestre sobre semana
            semana = None
    except ValueError:
        trimestre = None
    
    # Calcular los totales globales
    totales = calcular_totales_globales(anio, semana, trimestre)
    
    return JsonResponse(totales)
