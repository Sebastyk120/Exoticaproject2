import decimal

from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date
from decimal import Decimal
from django.db.models import Q, Sum
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from .models import Pedido, DetallePedido, Exportador, Bodega
from productos.models import Presentacion, ListaPreciosImportacion


@login_required
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
    paginator = Paginator(queryset, 5)  # Mostrar 10 pedidos por página
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


@login_required
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
                
            # Formatear valor_nc_usd_manual para mostrar correctamente en el formulario
            if detalle.valor_nc_usd_manual is not None:
                detalle.valor_nc_usd_manual_str = '{:.2f}'.format(detalle.valor_nc_usd_manual)
            else:
                detalle.valor_nc_usd_manual_str = '0.00'
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


@login_required
@require_POST
def guardar_pedido(request, pedido_id=None):
    """Handle saving the main order data"""
    try:
        with transaction.atomic():
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

            # Si es un pedido nuevo, buscar y procesar detalles nuevos
            if not pedido_id:
                import re
                new_pattern = r'new_(\d+)_(\w+)'
                new_indices = set()
                
                # Identificar índices de nuevos detalles
                for key in request.POST.keys():
                    match = re.match(new_pattern, key)
                    if match:
                        new_indices.add(match.group(1))
                
                # Procesar cada nuevo detalle
                for index in new_indices:
                    try:
                        # Verificar si los datos esenciales existen
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
                        detalle.valor_nc_usd_manual = Decimal(request.POST.get(f'new_{index}_valor_nc_usd_manual') or 0)
                        
                        # Validar que no_cajas_nc no sea mayor que cajas_recibidas
                        if detalle.no_cajas_nc > detalle.cajas_recibidas:
                            messages.error(request, 
                                        f'Error en detalle: El número de cajas NC no puede ser mayor que las cajas recibidas')
                            raise ValueError("NC boxes validation error")
                            
                        # Guardar el detalle
                        detalle.full_clean()  # Validar el modelo
                        detalle.save()
                    except (ValueError, TypeError, decimal.InvalidOperation) as e:
                        # Manejar errores de conversión
                        messages.error(request, f'Error al procesar detalle: {str(e)}')
                        raise  # Re-lanzar para que la transacción se revierta
                
                # Actualizar los totales del pedido después de añadir todos los detalles
                if new_indices:
                    from .models import DetallePedido
                    DetallePedido.actualizar_totales_pedido(pedido.id)

        messages.success(request, f'Pedido {pedido.id} guardado correctamente')
        return redirect('importacion:detalle_pedido', pedido_id=pedido.id)
    
    except Exception as e:
        messages.error(request, f'Error al guardar el pedido: {str(e)}')
        # Para un pedido nuevo, redirigir a la página de nuevo pedido
        if not pedido_id:
            return redirect('importacion:nuevo_pedido')
        # Para un pedido existente, redirigir a la página de detalles
        return redirect('importacion:detalle_pedido', pedido_id=pedido_id)


@login_required
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


@login_required
@require_POST
def guardar_detalles_batch(request, pedido_id):
    """Handle saving multiple order details at once"""
    from .signals import reevaluar_pagos_exportador, actualizar_stock_multiple
    from .models import get_cajas_vendidas
    from decimal import Decimal
    from django.db.models import Sum
    from django.db.models.functions import Coalesce

    pedido = get_object_or_404(Pedido, pk=pedido_id)

    # Primero verificamos si hay algún NC en los detalles y si el número NC del pedido es nulo
    numero_nc_pedido = request.POST.get('numero_nc', '').strip()
    tiene_detalles_nc = False

    # Verificar en detalles existentes
    for key in request.POST.keys():
        if '_no_cajas_nc' in key or '_valor_nc_usd_manual' in key:
            try:
                # Convertir a decimal para una comparación precisa
                valor = Decimal(request.POST.get(key, '0').strip() or '0')
                if valor > Decimal('0'):
                    tiene_detalles_nc = True
                    break
            except (ValueError, decimal.InvalidOperation):
                # Si hay error de conversión, ignorar este valor
                continue

    if tiene_detalles_nc and not numero_nc_pedido:
        messages.error(request, 'El campo Número NC del pedido no puede estar vacío si hay NC en algún detalle')
        return redirect('importacion:detalle_pedido', pedido_id=pedido.id)

    # Usar una transacción para garantizar consistencia en todas las operaciones
    with transaction.atomic():
        # Actualizar datos del pedido primero para tener el exportador actual
        pedido.exportador_id = request.POST.get('exportador')
        pedido.fecha_entrega = parse_date(request.POST.get('fecha_entrega'))
        pedido.awb = request.POST.get('awb')
        pedido.numero_factura = request.POST.get('numero_factura')
        pedido.numero_nc = request.POST.get('numero_nc')
        pedido.observaciones = request.POST.get('observaciones')
        pedido.save()

        # Variables para rastrear presentaciones afectadas para actualización de stock
        presentaciones_afectadas = set()
        
        # Capturar estado original para posible rollback
        originales = {}
        for detalle in DetallePedido.objects.filter(pedido=pedido).select_related('presentacion'):
            originales[detalle.id] = {
                'presentacion_id': detalle.presentacion_id,
                'cajas_recibidas': detalle.cajas_recibidas
            }
            presentaciones_afectadas.add(detalle.presentacion_id)

        # Verificar eliminaciones antes de procesar para validar el stock
        delete_ids = request.POST.getlist('delete_detail_ids')
        if delete_ids:
            # Primero validar cada eliminación antes de proceder
            for detalle_id in delete_ids:
                try:
                    detalle = DetallePedido.objects.select_related('presentacion').get(id=detalle_id, pedido=pedido)
                    if detalle.presentacion_id:
                        cajas_vendidas = get_cajas_vendidas(detalle.presentacion_id)
                        if cajas_vendidas > 0:
                            # Verificar si hay suficiente stock en otros detalles (excluyendo todos los que se eliminarán)
                            cajas_otros_detalles = DetallePedido.objects.filter(
                                presentacion_id=detalle.presentacion_id
                            ).exclude(id__in=delete_ids).exclude(pedido=pedido).aggregate(
                                total=Coalesce(Sum('cajas_recibidas'), 0)
                            )['total'] or 0
                            
                            if cajas_otros_detalles < cajas_vendidas:
                                messages.error(request, 
                                    f'No se puede eliminar el detalle #{detalle_id} porque ya se han vendido {cajas_vendidas} cajas '
                                    f'de {detalle.presentacion} y solo quedarían {cajas_otros_detalles} cajas disponibles en otros pedidos.')
                                return redirect('importacion:detalle_pedido', pedido_id=pedido.id)
                except DetallePedido.DoesNotExist:
                    continue
            
            # Si todas las validaciones pasan, proceder con las eliminaciones
            DetallePedido.objects.filter(id__in=delete_ids, pedido=pedido).delete()

        # Procesar detalles existentes (actualizaciones)
        existing_pattern = r'detalle_(\d+)_(\w+)'
        existing_ids = set()
        import re

        # Primero, identificar todos los IDs de detalles existentes
        for key in request.POST.keys():
            match = re.match(existing_pattern, key)
            if match:
                existing_ids.add(match.group(1))

        # Luego, actualizar cada detalle existente
        for detail_id in existing_ids:
            try:
                detalle = DetallePedido.objects.get(pk=detail_id, pedido=pedido)
                
                # Obtener valores originales para comparar cambios
                presentacion_id_original = detalle.presentacion_id
                cajas_recibidas_original = detalle.cajas_recibidas
                
                # Obtener valores para validación
                cajas_recibidas = int(request.POST.get(f'detalle_{detail_id}_cajas_recibidas') or 0)
                no_cajas_nc = Decimal(request.POST.get(f'detalle_{detail_id}_no_cajas_nc') or 0)
                valor_nc_usd_manual = Decimal(request.POST.get(f'detalle_{detail_id}_valor_nc_usd_manual') or 0)
                presentacion_id_nueva = request.POST.get(f'detalle_{detail_id}_presentacion')
                
                # Validar que no_cajas_nc no sea mayor que cajas_recibidas
                if no_cajas_nc > cajas_recibidas:
                    messages.error(request,
                                f'Error en detalle #{detail_id}: El número de cajas NC no puede ser mayor que las cajas recibidas')
                    return redirect('importacion:detalle_pedido', pedido_id=pedido.id)

                # Registrar presentaciones afectadas para actualización posterior
                if presentacion_id_original:
                    presentaciones_afectadas.add(presentacion_id_original)
                if presentacion_id_nueva:
                    presentaciones_afectadas.add(presentacion_id_nueva)

                # Asignar explícitamente el valor original para que la señal pueda detectar cambios
                detalle._original_cajas_recibidas = cajas_recibidas_original
                
                # Verificar si estamos cambiando la presentación o reduciendo cajas
                hay_cambio_presentacion = str(presentacion_id_original) != presentacion_id_nueva
                hay_reduccion_cajas = cajas_recibidas < cajas_recibidas_original
                
                # Validar cambio de presentación si ya hay ventas asociadas
                if hay_cambio_presentacion and presentacion_id_original:
                    cajas_vendidas = get_cajas_vendidas(presentacion_id_original)
                    if cajas_vendidas > 0:
                        # Verificar si hay suficiente stock en otros detalles
                        cajas_otros_detalles = DetallePedido.objects.filter(
                            presentacion_id=presentacion_id_original
                        ).exclude(pk=detail_id).aggregate(
                            total=Coalesce(Sum('cajas_recibidas'), 0)
                        )['total'] or 0
                        
                        if cajas_otros_detalles < cajas_vendidas:
                            messages.error(request,
                                f'No puede cambiar la presentación del detalle #{detail_id} porque ya se han vendido {cajas_vendidas} cajas '
                                f'y solo quedarían {cajas_otros_detalles} cajas disponibles en otros detalles.')
                            return redirect('importacion:detalle_pedido', pedido_id=pedido.id)
                
                # Validar reducción de cajas si ya hay ventas asociadas
                if hay_reduccion_cajas and presentacion_id_original:
                    cajas_vendidas = get_cajas_vendidas(presentacion_id_original)
                    if cajas_vendidas > 0:
                        # Calcular cajas totales de esta presentación (excluyendo este detalle)
                        cajas_otros_detalles = DetallePedido.objects.filter(
                            presentacion_id=presentacion_id_original
                        ).exclude(pk=detail_id).aggregate(
                            total=Coalesce(Sum('cajas_recibidas'), 0)
                        )['total'] or 0
                        
                        # Verificar si hay suficiente stock total
                        total_disponible = cajas_otros_detalles + cajas_recibidas
                        if total_disponible < cajas_vendidas:
                            messages.error(request,
                                f'No puede reducir a {cajas_recibidas} cajas el detalle #{detail_id}. '
                                f'Ya se han vendido {cajas_vendidas} cajas de esta presentación y '
                                f'solo habría {total_disponible} cajas en total.')
                            return redirect('importacion:detalle_pedido', pedido_id=pedido.id)

                # Actualizar campos
                detalle.presentacion_id = presentacion_id_nueva
                detalle.cajas_solicitadas = int(request.POST.get(f'detalle_{detail_id}_cajas_solicitadas') or 0)
                detalle.cajas_recibidas = cajas_recibidas
                detalle.valor_x_caja_usd = Decimal(request.POST.get(f'detalle_{detail_id}_valor_x_caja_usd') or 0)
                detalle.no_cajas_nc = no_cajas_nc
                detalle.valor_nc_usd_manual = valor_nc_usd_manual

                # Guardar el detalle, saltando la actualización de stock individual
                detalle._skip_stock_update = True  # Evitar que la señal post_save actualice el stock
                detalle.full_clean()  # Asegurar que se llame a clean()
                detalle.save()

            except (DetallePedido.DoesNotExist, ValueError, TypeError, decimal.InvalidOperation) as e:
                messages.error(request, f'Error al actualizar detalle #{detail_id}: {str(e)}')
                return redirect('importacion:detalle_pedido', pedido_id=pedido.id)

        # Procesar nuevos detalles
        new_pattern = r'new_(\d+)_(\w+)'
        new_indices = set()

        # Primero, identificar todos los índices de nuevos detalles
        for key in request.POST.keys():
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

                # Validar cajas NC vs cajas recibidas
                cajas_recibidas = int(request.POST.get(f'new_{index}_cajas_recibidas') or 0)
                no_cajas_nc = Decimal(request.POST.get(f'new_{index}_no_cajas_nc') or 0)
                valor_nc_usd_manual = Decimal(request.POST.get(f'new_{index}_valor_nc_usd_manual') or 0)

                if no_cajas_nc > cajas_recibidas:
                    messages.error(request,
                               f'Error en nuevo detalle: El número de cajas NC no puede ser mayor que las cajas recibidas')
                    return redirect('importacion:detalle_pedido', pedido_id=pedido.id)

                # Registrar presentación para actualización de stock
                presentaciones_afectadas.add(int(presentacion_id))

                # Crear nuevo detalle
                detalle = DetallePedido(pedido=pedido)
                detalle._skip_stock_update = True  # Evitar que la señal post_save actualice el stock
                detalle._original_cajas_recibidas = 0  # Nueva inserción, valor original es 0
                
                detalle.presentacion_id = presentacion_id
                detalle.cajas_solicitadas = int(request.POST.get(f'new_{index}_cajas_solicitadas') or 0)
                detalle.cajas_recibidas = cajas_recibidas
                detalle.valor_x_caja_usd = Decimal(request.POST.get(f'new_{index}_valor_x_caja_usd') or 0)
                detalle.no_cajas_nc = no_cajas_nc
                detalle.valor_nc_usd_manual = valor_nc_usd_manual

                # Guardar el detalle para disparar las señales
                detalle.full_clean()  # Asegurar que se llame a clean()
                detalle.save()

            except (ValueError, TypeError, decimal.InvalidOperation) as e:
                messages.error(request, f'Error al crear nuevo detalle: {str(e)}')
                return redirect('importacion:detalle_pedido', pedido_id=pedido.id)

        # Actualizar el stock para todas las presentaciones afectadas de una sola vez
        # usando nuestra función optimizada desde el módulo signals
        actualizar_stock_multiple(presentaciones_afectadas)

        # Forzar la reevaluación del pedido y sus totales
        DetallePedido.actualizar_totales_pedido(pedido.id)

        # Forzar explícitamente la reevaluación de pagos del exportador después de todos los cambios
        reevaluar_pagos_exportador(pedido.exportador)

    # Refrescar el objeto pedido desde la base de datos para tener datos actualizados
    pedido.refresh_from_db()

    messages.success(request, 'Pedido y detalles guardados correctamente')
    
    # Verificar si se debe redirigir a solicitar_pedido
    if request.POST.get('enviar_solicitud') == 'true':
        redirect_url = request.POST.get('redirect_url')
        if redirect_url:
            return redirect(redirect_url)
    
    return redirect('importacion:detalle_pedido', pedido_id=pedido.id)


def nuevo_pedido(request):
    """View to create a new order"""
    context = {
        'pedido': None,
        'detalles': [],
        'exportadores': Exportador.objects.all(),
        'presentaciones': Presentacion.objects.all().select_related('fruta'),
    }
    return render(request, 'pedidos/pedidos.html', context)


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
        'total_usd': f"${pedido.valor_total_factura_usd or 0:.2f}",
        'total_eur': f"€{pedido.valor_factura_eur or 0:.2f}" if pedido.valor_factura_eur else "-"
    }

    # Detalles de los productos
    detalles_data = []
    for detalle in detalles:
        # Calcular el valor total de NC sumando valor_nc_usd y valor_nc_usd_manual
        total_nc = (detalle.valor_nc_usd or 0) + (detalle.valor_nc_usd_manual or 0)
        
        detalles_data.append({
            'producto': detalle.presentacion.fruta.nombre,
            'presentacion': f"{detalle.presentacion.fruta} {detalle.presentacion.kilos}kg",
            'kilos': f"{detalle.kilos or 0:.2f}",
            'cajas_solicitadas': detalle.cajas_solicitadas or 0,
            'cajas_recibidas': detalle.cajas_recibidas or 0,
            'valor_caja': f"${detalle.valor_x_caja_usd or 0:.2f}",
            'valor_total': f"${detalle.valor_x_producto or 0:.2f}",
            'cajas_nc': f"{detalle.no_cajas_nc or 0:.1f}",
            'valor_nc': f"${total_nc:.2f}",
            'valor_total_eur': f"€{detalle.valor_x_producto_eur or 0:.2f}" if detalle.valor_x_producto_eur and detalle.valor_x_producto_eur > 0 else None
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

        if (precio):
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


@login_required
def solicitar_pedido(request, pedido_id):
    """View to display the order request form"""
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    detalles = DetallePedido.objects.filter(pedido=pedido).select_related('presentacion', 'presentacion__fruta')

    return render(request, 'pedidos/solicitar_pedido.html', {
        'pedido': pedido,
        'detalles': detalles,
    })