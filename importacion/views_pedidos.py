import decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date
from decimal import Decimal
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Pedido, DetallePedido, Exportador
from productos.models import Presentacion, ListaPreciosImportacion

def lista_pedidos(request):
    """View to list all orders with search and filter functionality"""
    # Iniciar con todos los pedidos
    queryset = Pedido.objects.all().select_related('exportador')
    
    # Buscar por término de búsqueda
    search_query = request.GET.get('q', '')
    if search_query:
        queryset = queryset.filter(
            Q(awb__icontains=search_query) |
            Q(exportador__nombre__icontains=search_query) |
            Q(numero_factura__icontains=search_query) |
            Q(semana__icontains=search_query)
        )
    
    # Filtrar por estado
    estado_filter = request.GET.get('estado', '')
    if estado_filter:
        queryset = queryset.filter(estado_pedido=estado_filter)
    
    # Ordenar los resultados (más recientes primero)
    queryset = queryset.order_by('-id')
    
    # Implementar paginación
    paginator = Paginator(queryset, 20)  # Mostrar 20 pedidos por página
    page = request.GET.get('page')
    
    try:
        pedidos = paginator.page(page)
    except PageNotAnInteger:
        # Si la página no es un entero, mostrar la primera página
        pedidos = paginator.page(1)
    except EmptyPage:
        # Si la página está fuera de rango, mostrar la última página de resultados
        pedidos = paginator.page(paginator.num_pages)
    
    return render(request, 'pedidos/lista_pedidos.html', {
        'pedidos': pedidos,
        'search_query': search_query,
        'estado_filter': estado_filter,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': pedidos,
    })

def detalle_pedido(request, pedido_id=None):
    """View to display and edit a specific order"""
    if pedido_id:
        pedido = get_object_or_404(Pedido, pk=pedido_id)
        # Use select_related for both presentacion and fruta to fully load the relationships
        detalles = DetallePedido.objects.filter(pedido=pedido).select_related('presentacion', 'presentacion__fruta')
        
        # Debug the detalles to ensure values are being retrieved correctly
        for detalle in detalles:
            # Convert decimal values to strings to ensure proper formatting in template
            if detalle.valor_x_caja_usd is not None:
                detalle.valor_x_caja_usd_str = '{:.2f}'.format(detalle.valor_x_caja_usd)
            else:
                detalle.valor_x_caja_usd_str = '0.00'
                
            if detalle.no_cajas_nc is not None:
                detalle.no_cajas_nc_str = '{:.1f}'.format(detalle.no_cajas_nc)
            else:
                detalle.no_cajas_nc_str = '0.0'
    else:
        pedido = None
        detalles = []
    
    # For dropdown selections
    exportadores = Exportador.objects.all()
    # Include fruta to avoid additional queries when displaying presentaciones
    presentaciones = Presentacion.objects.all().select_related('fruta')
    
    context = {
        'pedido': pedido,
        'detalles': detalles,
        'exportadores': exportadores,
        'presentaciones': presentaciones,
    }
    
    return render(request, 'pedidos/pedidos.html', context)

@require_POST
def guardar_pedido(request, pedido_id=None):
    """Handle saving the main order data"""
    if pedido_id:
        pedido = get_object_or_404(Pedido, pk=pedido_id)
    else:
        pedido = Pedido()
    
    # Get form data
    pedido.exportador_id = request.POST.get('exportador')
    pedido.fecha_entrega = parse_date(request.POST.get('fecha_entrega'))
    pedido.awb = request.POST.get('awb')
    pedido.numero_factura = request.POST.get('numero_factura')
    pedido.numero_nc = request.POST.get('numero_nc')
    pedido.observaciones = request.POST.get('observaciones')
    
    # Save the order
    pedido.save()
    
    messages.success(request, f'Pedido {pedido.id} guardado correctamente')
    return redirect('importacion:detalle_pedido', pedido_id=pedido.id)

@require_POST
def guardar_detalle(request, pedido_id, detalle_id=None):
    """Handle saving an order detail item"""
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    
    if detalle_id:
        detalle = get_object_or_404(DetallePedido, pk=detalle_id, pedido=pedido)
    else:
        detalle = DetallePedido(pedido=pedido)
    
    # Get form data with explicit handling for each field
    try:
        detalle.presentacion_id = request.POST.get('presentacion')
        detalle.cajas_solicitadas = int(request.POST.get('cajas_solicitadas') or 0)
        detalle.cajas_recibidas = int(request.POST.get('cajas_recibidas') or 0)
        detalle.valor_x_caja_usd = Decimal(request.POST.get('valor_x_caja_usd') or 0)
        detalle.no_cajas_nc = Decimal(request.POST.get('no_cajas_nc') or 0)
    except (ValueError, TypeError, decimal.InvalidOperation):
        # Handle conversion errors gracefully
        messages.error(request, 'Error al procesar algunos valores numéricos. Por favor, verifique los datos.')
        return redirect('importacion:detalle_pedido', pedido_id=pedido.id)
    
    # Save the detail
    detalle.save()
    
    # Return JSON for AJAX or redirect for standard form submission
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'detalle_id': detalle.id})
    
    messages.success(request, 'Detalle de pedido guardado correctamente')
    return redirect('importacion:detalle_pedido', pedido_id=pedido.id)

@require_POST
def guardar_detalles_batch(request, pedido_id):
    """Handle saving multiple order details at once"""
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    
    # Procesar eliminaciones
    delete_ids = request.POST.getlist('delete_detail_ids')
    if delete_ids:
        DetallePedido.objects.filter(id__in=delete_ids, pedido=pedido).delete()
    
    # Obtener todas las claves del formulario
    form_keys = request.POST.keys()
    
    # Procesar detalles existentes (actualizaciones)
    existing_pattern = r'detalle_(\d+)_(\w+)'
    existing_ids = set()
    import re
    
    # Primero, identificar todos los IDs de detalles existentes
    for key in form_keys:
        match = re.match(existing_pattern, key)
        if match:
            existing_ids.add(match.group(1))
    
    # Luego, actualizar cada detalle existente
    for detail_id in existing_ids:
        try:
            detalle = DetallePedido.objects.get(pk=detail_id, pedido=pedido)
            
            # Actualizar campos
            detalle.presentacion_id = request.POST.get(f'detalle_{detail_id}_presentacion')
            detalle.cajas_solicitadas = int(request.POST.get(f'detalle_{detail_id}_cajas_solicitadas') or 0)
            detalle.cajas_recibidas = int(request.POST.get(f'detalle_{detail_id}_cajas_recibidas') or 0)
            detalle.valor_x_caja_usd = Decimal(request.POST.get(f'detalle_{detail_id}_valor_x_caja_usd') or 0)
            detalle.no_cajas_nc = Decimal(request.POST.get(f'detalle_{detail_id}_no_cajas_nc') or 0)
            
            detalle.save()
        except (DetallePedido.DoesNotExist, ValueError, TypeError, decimal.InvalidOperation) as e:
            messages.error(request, f'Error al actualizar detalle #{detail_id}: {str(e)}')
    
    # Procesar nuevos detalles
    new_pattern = r'new_(\d+)_(\w+)'
    new_indices = set()
    
    # Primero, identificar todos los índices de nuevos detalles
    for key in form_keys:
        match = re.match(new_pattern, key)
        if match:
            new_indices.add(match.group(1))
    
    # Luego, crear cada nuevo detalle
    for index in new_indices:
        try:
            # Obtener campos del formulario
            presentacion_id = request.POST.get(f'new_{index}_presentacion')
            if not presentacion_id:  # Ignorar filas incompletas
                continue
                
            # Crear nuevo detalle
            detalle = DetallePedido(pedido=pedido)
            detalle.presentacion_id = presentacion_id
            detalle.cajas_solicitadas = int(request.POST.get(f'new_{index}_cajas_solicitadas') or 0)
            detalle.cajas_recibidas = int(request.POST.get(f'new_{index}_cajas_recibidas') or 0)
            detalle.valor_x_caja_usd = Decimal(request.POST.get(f'new_{index}_valor_x_caja_usd') or 0)
            detalle.no_cajas_nc = Decimal(request.POST.get(f'new_{index}_no_cajas_nc') or 0)
            
            detalle.save()
        except (ValueError, TypeError, decimal.InvalidOperation) as e:
            messages.error(request, f'Error al crear nuevo detalle: {str(e)}')
    
    messages.success(request, 'Detalles del pedido guardados correctamente')
    return redirect('importacion:detalle_pedido', pedido_id=pedido.id)

def nuevo_pedido(request):
    """View to create a new order"""
    return detalle_pedido(request)

def obtener_detalles_pedido(request, pedido_id):
    """Vista para obtener los detalles de un pedido en formato JSON para el modal"""
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    detalles = DetallePedido.objects.filter(pedido=pedido).select_related('presentacion', 'presentacion__fruta')
    
    # Información básica del pedido
    pedido_data = {
        'id': pedido.id,
        'exportador': pedido.exportador.nombre,
        'fecha_entrega': pedido.fecha_entrega.strftime('%d/%m/%Y'),
        'awb': pedido.awb or '-',
        'total_cajas': f"{pedido.total_cajas_recibidas}/{pedido.total_cajas_solicitadas}",
        'total_usd': f"${pedido.valor_total_factura_usd or 0:.2f}"
    }
    
    # Detalles de los productos
    detalles_data = []
    for detalle in detalles:
        detalles_data.append({
            'producto': detalle.presentacion.fruta.nombre,
            'presentacion': f"{detalle.presentacion.fruta} {detalle.presentacion.kilos}kg",
            'kilos': f"{detalle.kilos or 0:.2f}",
            'cajas_solicitadas': detalle.cajas_solicitadas or 0,
            'cajas_recibidas': detalle.cajas_recibidas or 0,
            'valor_caja': f"${detalle.valor_x_caja_usd or 0:.2f}",
            'valor_total': f"${detalle.valor_x_producto or 0:.2f}",
            'cajas_nc': f"{detalle.no_cajas_nc or 0:.1f}",
            'valor_nc': f"${detalle.valor_nc_usd or 0:.2f}"
        })
    
    return JsonResponse({
        'pedido': pedido_data,
        'detalles': detalles_data
    })

def obtener_precio_presentacion(request, presentacion_id, exportador_id):
    """API endpoint to get the price for a presentation from a specific exporter"""
    # Validar IDs
    try:
        presentacion_id = int(presentacion_id)
        exportador_id = int(exportador_id)
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'IDs de presentación o exportador inválidos'
        }, status=400)
    
    try:
        # Verificar que existan la presentación y el exportador
        if not Presentacion.objects.filter(id=presentacion_id).exists():
            return JsonResponse({
                'success': False,
                'message': 'La presentación especificada no existe'
            }, status=404)
            
        if not Exportador.objects.filter(id=exportador_id).exists():
            return JsonResponse({
                'success': False,
                'message': 'El exportador especificado no existe'
            }, status=404)
        
        # Intentar obtener el precio de la lista de precios
        precio = ListaPreciosImportacion.objects.filter(
            presentacion_id=presentacion_id,
            exportador_id=exportador_id
        ).first()
        
        if precio:
            # Si existe un precio para esta combinación de presentación y exportador
            return JsonResponse({
                'success': True,
                'precio': float(precio.precio_usd)
            })
        else:
            # Si no hay precio configurado
            return JsonResponse({
                'success': False,
                'message': 'No hay precio configurado para esta presentación y exportador'
            }, status=404)
    except Exception as e:
        # En caso de error, registrar la excepción para depuración
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error al obtener precio: {str(e)}', exc_info=True)
        
        return JsonResponse({
            'success': False,
            'message': f'Error al obtener el precio: {str(e)}'
        }, status=500)

def solicitar_pedido(request, pedido_id):
    """View to display the order request form"""
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    detalles = DetallePedido.objects.filter(pedido=pedido).select_related('presentacion', 'presentacion__fruta')
    
    return render(request, 'pedidos/solicitar_pedido.html', {
        'pedido': pedido,
        'detalles': detalles,
    })
