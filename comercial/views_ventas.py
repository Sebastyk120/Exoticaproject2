import decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date
from decimal import Decimal
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from .models import Venta, DetalleVenta, Cliente, BalanceCliente
from productos.models import Presentacion, ListaPreciosVentas
from django.core.exceptions import ValidationError
from importacion.models import Bodega, Pedido

@login_required
def lista_ventas(request):
    """View to list all sales with search and filter functionality"""
    # Iniciar con todas las ventas
    queryset = Venta.objects.all().select_related('cliente')
    
    # Buscar por término de búsqueda
    search_query = request.GET.get('q', '')
    if search_query:
        queryset = queryset.filter(
            Q(numero_factura__icontains=search_query) |
            Q(cliente__nombre__icontains=search_query) |
            Q(semana__icontains=search_query)
        )
    
    # Filtrar por estado de pago
    pagado_filter = request.GET.get('pagado', '')
    if pagado_filter:
        pagado_bool = pagado_filter == 'Si'
        queryset = queryset.filter(pagado=pagado_bool)
    
    # Ordenar los resultados (más recientes primero)
    queryset = queryset.order_by('-id')
    
    # Implementar paginación
    paginator = Paginator(queryset, 10)  # Mostrar 10 ventas por página
    page = request.GET.get('page')
    
    try:
        ventas = paginator.page(page)
    except PageNotAnInteger:
        # Si la página no es un entero, mostrar la primera página
        ventas = paginator.page(1)
    except EmptyPage:
        # Si la página está fuera de rango, mostrar la última página de resultados
        ventas = paginator.page(paginator.num_pages)
    
    return render(request, 'ventas/lista_ventas.html', {
        'ventas': ventas,
        'search_query': search_query,
        'pagado_filter': pagado_filter,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': ventas,
    })

@login_required
def detalle_venta(request, venta_id=None):
    """View to display and edit a specific sale"""
    if venta_id:
        venta = get_object_or_404(Venta, pk=venta_id)
        # Use select_related for both presentacion and fruta to fully load the relationships
        detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
        
        # Format decimal values for proper display in template
        for detalle in detalles:
            if detalle.valor_x_caja_euro is not None:
                detalle.valor_x_caja_euro_str = '{:.2f}'.format(detalle.valor_x_caja_euro)
            else:
                detalle.valor_x_caja_euro_str = '0.00'
                
            if detalle.no_cajas_abono is not None:
                detalle.no_cajas_abono_str = '{:.1f}'.format(detalle.no_cajas_abono)
            else:
                detalle.no_cajas_abono_str = '0.0'
    else:
        venta = None
        detalles = []
    
    # For dropdown selections
    clientes = Cliente.objects.all()
    # Include fruta to avoid additional queries when displaying presentaciones
    presentaciones = Presentacion.objects.all().select_related('fruta')
    
    # Get pedidos for the selector
    if venta:
        # Si es una venta existente, obtener los últimos 5 pedidos y los pedidos asignados
        pedidos_asignados = venta.pedidos.all()
        ultimos_pedidos = Pedido.objects.exclude(id__in=pedidos_asignados).order_by('-fecha_entrega')[:5]
        # Combinar los pedidos asignados con los últimos pedidos, eliminando duplicados
        todos_pedidos = list(pedidos_asignados) + list(ultimos_pedidos)
        # Eliminar duplicados manteniendo el orden
        todos_pedidos = list(dict.fromkeys(todos_pedidos))
    else:
        # Si es una nueva venta, obtener los últimos 5 pedidos
        todos_pedidos = Pedido.objects.all().order_by('-fecha_entrega')[:5]
    
    context = {
        'venta': venta,
        'detalles': detalles,
        'clientes': clientes,
        'presentaciones': presentaciones,
        'ultimos_pedidos': todos_pedidos,  # Cambiamos el nombre de la variable para reflejar que ahora incluye todos los pedidos relevantes
    }
    
    return render(request, 'ventas/ventas.html', context)

@login_required
@require_POST
def guardar_venta(request, venta_id=None):
    """Handle saving the main sale data"""
    try:
        if venta_id:
            venta = get_object_or_404(Venta, pk=venta_id)
        else:
            venta = Venta()
        
        # Validar cliente
        cliente_id = request.POST.get('cliente')
        if not cliente_id:
            return JsonResponse({'success': False, 'message': 'Debe seleccionar un cliente.'}, status=400)
        
        try:
            cliente = Cliente.objects.get(id=cliente_id)
            venta.cliente = cliente
        except Cliente.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'El cliente seleccionado no existe.'}, status=400)
        
        # Validar que se haya seleccionado al menos un pedido
        pedidos_seleccionados = request.POST.getlist('pedidos')
        if not pedidos_seleccionados:
            return JsonResponse({'success': False, 'message': 'Debe seleccionar al menos un pedido.'}, status=400)
        
        # Validar y obtener la fecha de entrega
        fecha_entrega_str = request.POST.get('fecha_entrega')
        if not fecha_entrega_str:
            from django.utils import timezone
            venta.fecha_entrega = timezone.now().date()
        else:
            try:
                venta.fecha_entrega = parse_date(fecha_entrega_str)
                if not venta.fecha_entrega:
                    raise ValueError('Fecha inválida')
            except (ValueError, TypeError) as e:
                return JsonResponse({'success': False, 'message': f'La fecha de entrega no es válida. Detalle: {str(e)}'}, status=400)
        
        # Obtener la fecha de compra del primer pedido seleccionado
        try:
            primer_pedido = Pedido.objects.get(id=pedidos_seleccionados[0])
            venta.fecha_compra = primer_pedido.fecha_entrega
            venta.semana = primer_pedido.semana
        except Pedido.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Uno de los pedidos seleccionados no existe.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error al procesar el pedido: {str(e)}'}, status=400)
        
        # Capturar el porcentaje de IVA del formulario
        try:
            iva_str = request.POST.get('porcentaje_iva', '4.00')
            venta.porcentaje_iva = Decimal(iva_str)
        except (ValueError, decimal.InvalidOperation):
            venta.porcentaje_iva = Decimal('4.00')
        
        # Otros campos
        venta.numero_nc = request.POST.get('numero_nc', '')
        venta.observaciones = request.POST.get('observaciones', '')
        venta.origen = request.POST.get('origen', '')
        
        # Guardar la venta primero para que tenga un ID
        venta.save()
        
        # Asociar los pedidos
        venta.pedidos.set(pedidos_seleccionados)
        
        # Actualizar la semana basada en los pedidos asociados
        pedidos_actuales = venta.pedidos.all()
        if pedidos_actuales.exists():
            primer_pedido = pedidos_actuales.first()
            if primer_pedido and primer_pedido.semana:
                venta.semana = primer_pedido.semana
                venta.save(update_fields=['semana'])
        
        # Check if the request is AJAX and respond with JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Venta {venta.id} guardada correctamente',
                'venta_id': venta.id
            })
        
        messages.success(request, f'Venta {venta.id} guardada correctamente')
        return redirect('comercial:detalle_venta', venta_id=venta.id)
        
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f'Error al guardar la venta: {str(e)}'
            }, status=500)
        
        messages.error(request, f'Error al guardar la venta: {str(e)}')
        return redirect('comercial:lista_ventas')

@login_required
@require_POST
def guardar_detalle(request, venta_id, detalle_id=None):
    """Handle saving a sale detail item"""
    venta = get_object_or_404(Venta, pk=venta_id)
    
    if detalle_id:
        detalle = get_object_or_404(DetalleVenta, pk=detalle_id, venta=venta)
    else:
        detalle = DetalleVenta(venta=venta)
    
    # Get form data with explicit handling for each field
    try:
        detalle.presentacion_id = request.POST.get('presentacion')
        detalle.cajas_enviadas = int(request.POST.get('cajas_enviadas') or 0)
        valor_caja = Decimal(request.POST.get('valor_x_caja_euro') or 0)
        
        # Validar que el valor de la caja sea mayor que 0
        if valor_caja <= 0:
            messages.error(request, 'El valor de la caja debe ser mayor que 0.')
            return redirect('comercial:detalle_venta', venta_id=venta.id)
            
        detalle.valor_x_caja_euro = valor_caja
        detalle.no_cajas_abono = Decimal(request.POST.get('no_cajas_abono') or 0)
    except (ValueError, TypeError, decimal.InvalidOperation):
        # Handle conversion errors gracefully
        messages.error(request, 'Error al procesar algunos valores numéricos. Por favor, verifique los datos.')
        return redirect('comercial:detalle_venta', venta_id=venta.id)
    
    # Save the detail
    detalle.save()
    
    # Return JSON for AJAX or redirect for standard form submission
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'detalle_id': detalle.id})
    
    messages.success(request, 'Detalle de venta guardado correctamente')
    return redirect('comercial:detalle_venta', venta_id=venta.id)

@login_required
@require_POST
def guardar_detalles_batch(request, venta_id):
    """Handle saving multiple sale details at once"""
    venta = get_object_or_404(Venta, pk=venta_id)
    
    # Procesar eliminaciones
    delete_ids = request.POST.getlist('delete_detail_ids')
    if delete_ids:
        DetalleVenta.objects.filter(id__in=delete_ids, venta=venta).delete()
    
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
            detalle = DetalleVenta.objects.get(pk=detail_id, venta=venta)
            
            # Actualizar campos
            detalle.presentacion_id = request.POST.get(f'detalle_{detail_id}_presentacion')
            detalle.cajas_enviadas = int(request.POST.get(f'detalle_{detail_id}_cajas_enviadas') or 0)
            
            valor_caja = Decimal(request.POST.get(f'detalle_{detail_id}_valor_x_caja_euro') or 0)
            if valor_caja <= 0:
                messages.error(request, f'El valor de la caja en detalle #{detail_id} debe ser mayor que 0.')
                return redirect('comercial:detalle_venta', venta_id=venta.id)
            
            detalle.valor_x_caja_euro = valor_caja
            detalle.no_cajas_abono = Decimal(request.POST.get(f'detalle_{detail_id}_no_cajas_abono') or 0)
            
            detalle.save()
        except ValidationError as e:
            # Manejar errores de validación específicos
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, f'Error en detalle #{detail_id}: {error}')
            return redirect('comercial:detalle_venta', venta_id=venta.id)
        except (DetalleVenta.DoesNotExist, ValueError, TypeError, decimal.InvalidOperation) as e:
            messages.error(request, f'Error al actualizar detalle #{detail_id}: {str(e)}')
            return redirect('comercial:detalle_venta', venta_id=venta.id)
    
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
            detalle = DetalleVenta(venta=venta)
            detalle.presentacion_id = presentacion_id
            detalle.cajas_enviadas = int(request.POST.get(f'new_{index}_cajas_enviadas') or 0)
            
            valor_caja = Decimal(request.POST.get(f'new_{index}_valor_x_caja_euro') or 0)
            if valor_caja <= 0:
                messages.error(request, f'El valor de la caja en nuevo detalle debe ser mayor que 0.')
                return redirect('comercial:detalle_venta', venta_id=venta.id)
            
            detalle.valor_x_caja_euro = valor_caja
            detalle.no_cajas_abono = Decimal(request.POST.get(f'new_{index}_no_cajas_abono') or 0)
            
            detalle.save()
        except ValidationError as e:
            # Manejar errores de validación específicos
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, f'Error en nuevo detalle: {error}')
            return redirect('comercial:detalle_venta', venta_id=venta.id)
        except (ValueError, TypeError, decimal.InvalidOperation) as e:
            messages.error(request, f'Error al crear nuevo detalle: {str(e)}')
            return redirect('comercial:detalle_venta', venta_id=venta.id)
    
    messages.success(request, 'Detalles de la venta guardados correctamente')
    return redirect('comercial:detalle_venta', venta_id=venta.id)

@login_required
def nueva_venta(request):
    """View to create a new sale"""
    # Obtener los últimos 5 pedidos para la nueva venta
    todos_pedidos = Pedido.objects.all().order_by('-fecha_entrega')[:5]
    
    context = {
        'venta': None,
        'detalles': [],
        'clientes': Cliente.objects.all(),
        'presentaciones': Presentacion.objects.all().select_related('fruta'),
        'ultimos_pedidos': todos_pedidos,  # Añadir los pedidos al contexto
    }
    return render(request, 'ventas/ventas.html', context)

@login_required
def obtener_detalles_venta(request, venta_id):
    """Vista para obtener los detalles de una venta en formato JSON para el modal"""
    venta = get_object_or_404(Venta, pk=venta_id)
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
    
    # Información básica de la venta
    venta_data = {
        'id': venta.id,
        'cliente': venta.cliente.nombre,
        'fecha_entrega': venta.fecha_entrega.strftime('%d/%m/%Y'),
        'fecha_vencimiento': venta.fecha_vencimiento.strftime('%d/%m/%Y') if venta.fecha_vencimiento else '-',
        'total_cajas': f"{venta.total_cajas_pedido or 0}",
        'total_euros': f"€{venta.valor_total_factura_euro or 0:.2f}"
    }
    
    # Detalles de los productos
    detalles_data = []
    for detalle in detalles:
        detalles_data.append({
            'producto': detalle.presentacion.fruta.nombre,
            'presentacion': f"{detalle.presentacion.fruta} {detalle.presentacion.kilos}kg",
            'kilos': f"{detalle.kilos or 0:.2f}",
            'cajas_enviadas': detalle.cajas_enviadas or 0,
            'valor_caja': f"€{detalle.valor_x_caja_euro or 0:.2f}",
            'valor_total': f"€{detalle.valor_x_producto or 0:.2f}",
            'cajas_abono': f"{detalle.no_cajas_abono or 0:.1f}",
            'valor_abono': f"€{detalle.valor_abono_euro or 0:.2f}"
        })
    
    return JsonResponse({
        'venta': venta_data,
        'detalles': detalles_data
    })

@login_required
def obtener_precio_presentacion(request, presentacion_id, cliente_id):
    """API endpoint to get the price for a presentation from a specific client"""
    # Validar IDs
    try:
        presentacion_id = int(presentacion_id)
        cliente_id = int(cliente_id)
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'IDs de presentación o cliente inválidos'
        }, status=400)
    
    try:
        # Verificar que existan la presentación y el cliente
        if not Presentacion.objects.filter(id=presentacion_id).exists():
            return JsonResponse({
                'success': False,
                'message': 'La presentación especificada no existe'
            }, status=404)
            
        if not Cliente.objects.filter(id=cliente_id).exists():
            return JsonResponse({
                'success': False,
                'message': 'El cliente especificado no existe'
            }, status=404)
        
        # Intentar obtener el precio de la lista de precios
        precio = ListaPreciosVentas.objects.filter(
            presentacion_id=presentacion_id,
            cliente_id=cliente_id
        ).first()
        
        if precio:
            # Si existe un precio para esta combinación de presentación y cliente
            return JsonResponse({
                'success': True,
                'precio': float(precio.precio_euro)
            })
        else:
            # Si no hay precio configurado
            return JsonResponse({
                'success': False,
                'message': 'No hay precio configurado para esta presentación y cliente'
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
def generar_factura(request, venta_id):
    """View to generate the invoice for a sale"""
    venta = get_object_or_404(Venta, pk=venta_id)
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
    
    return render(request, 'ventas/generar_factura.html', {
        'venta': venta,
        'detalles': detalles,
    })

@login_required
def generar_rectificativa(request, venta_id):
    """View to generate the rectification invoice for a sale"""
    venta = get_object_or_404(Venta, pk=venta_id)
    
    # Only allow access if the sale has a credit note number
    if not venta.numero_nc:
        messages.error(request, "Esta venta no tiene una factura rectificativa asociada.")
        return redirect('comercial:generar_factura', venta_id=venta_id)
    
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
    
    # Get the IVA percentage and calculate the factor for removing IVA
    iva_percentage = venta.porcentaje_iva
    iva_factor = 1 + (iva_percentage / 100)
    
    # Calculate base_imponible for each detail
    for detalle in detalles:
        if detalle.valor_abono_euro:
            detalle.base_imponible = detalle.valor_abono_euro / Decimal(str(iva_factor))
        else:
            detalle.base_imponible = Decimal('0')
    
    # If iva_abono doesn't exist as a model field, calculate it
    if not hasattr(venta, 'iva_abono'):
        venta.total_base_imponible = venta.valor_total_abono_euro / Decimal(str(iva_factor))
        venta.iva_abono = venta.total_base_imponible * (iva_percentage / 100)
    
    # If valor_total_abono_euro_con_iva doesn't exist as a model field, calculate it
    if not hasattr(venta, 'valor_total_abono_euro_con_iva'):
        venta.valor_total_abono_euro_con_iva = venta.valor_total_abono_euro
        
    # Calculate the total number of boxes in the credit note
    if not hasattr(venta, 'total_cajas_abono') or venta.total_cajas_abono is None:
        venta.total_cajas_abono = sum(
            detalle.no_cajas_abono for detalle in detalles 
            if detalle.no_cajas_abono is not None
        )
    
    return render(request, 'ventas/generar_rectificativa.html', {
        'venta': venta,
        'detalles': detalles,
    })

@login_required
def validar_stock(request, presentacion_id, cajas_enviadas):
    """API endpoint para validar el stock disponible"""
    try:
        presentacion_id = int(presentacion_id)
        cajas_enviadas = int(cajas_enviadas)
        detalle_id = request.GET.get('detalle_id')
        
        if detalle_id:
            try:
                detalle_id = int(detalle_id)
            except ValueError:
                detalle_id = None
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'Valores inválidos'
        }, status=400)
    
    try:
        # Obtener la presentación
        presentacion = Presentacion.objects.get(id=presentacion_id)
        
        # Obtener el stock disponible
        bodega = Bodega.objects.get(presentacion=presentacion)
        stock_disponible = bodega.stock_actual
        
        # Si estamos editando un detalle existente, sumar las cajas que ya tiene ese detalle
        if detalle_id:
            try:
                detalle_existente = DetalleVenta.objects.get(id=detalle_id)
                # Añadir las cajas que ya están asignadas a este detalle
                stock_disponible += detalle_existente.cajas_enviadas
            except DetalleVenta.DoesNotExist:
                # Si no se encuentra el detalle, continuamos con el stock normal
                pass
        
        if stock_disponible < cajas_enviadas:
            return JsonResponse({
                'success': False,
                'message': f'Stock insuficiente. Solo hay {stock_disponible} cajas disponibles de {presentacion.fruta.nombre} - {presentacion.kilos} Kg',
                'stock_disponible': stock_disponible  # Incluir stock disponible para cálculos en frontend
            })
        
        return JsonResponse({
            'success': True,
            'message': 'Stock suficiente',
            'stock_disponible': stock_disponible  # Incluir también en respuesta exitosa
        })
        
    except Presentacion.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'La presentación especificada no existe'
        }, status=404)
    except Bodega.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': f'No existe registro de stock para {presentacion.fruta.nombre} - {presentacion.kilos} Kg'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al validar stock: {str(e)}'
        }, status=500)

@login_required
def generar_albaran(request, venta_id):
    """View to generate the delivery note (albarán) for a sale"""
    venta = get_object_or_404(Venta, pk=venta_id)
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
    
    return render(request, 'ventas/generar_albaran.html', {
        'venta': venta,
        'detalles': detalles,
    })

@login_required
def generar_albaran_cliente(request, venta_id):
    """View to generate a client delivery note (albarán) with prices for a sale"""
    venta = get_object_or_404(Venta, pk=venta_id)
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
    
    return render(request, 'ventas/generar_albaran_cliente.html', {
        'venta': venta,
        'detalles': detalles,
    })

def factura_cliente_token(request, venta_id, token):
    """Vista para que clientes puedan ver y descargar facturas mediante token"""
    # Verificar que el token sea válido
    cliente = get_object_or_404(Cliente, token_acceso=token)
    
    # Verificar que la venta corresponda al cliente que tiene el token
    venta = get_object_or_404(Venta, pk=venta_id, cliente=cliente)
    
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
    
    return render(request, 'ventas/factura_cliente_token.html', {
        'venta': venta,
        'detalles': detalles,
        'token': token
    })

def rectificativa_cliente_token(request, venta_id, token):
    """Vista para que clientes puedan ver y descargar facturas rectificativas mediante token"""
    # Verificar que el token sea válido
    cliente = get_object_or_404(Cliente, token_acceso=token)
    
    # Verificar que la venta corresponda al cliente que tiene el token
    venta = get_object_or_404(Venta, pk=venta_id, cliente=cliente)
    
    # Solo permitir acceso si la venta tiene una nota de crédito
    if not venta.numero_nc:
        messages.error(request, "Esta venta no tiene una factura rectificativa asociada.")
        return redirect('comercial:factura_cliente_token', venta_id=venta_id, token=token)
    
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
    
    # Get the IVA percentage and calculate the factor for removing IVA
    iva_percentage = venta.porcentaje_iva
    iva_factor = 1 + (iva_percentage / 100)
    
    # Calculate base_imponible for each detail
    for detalle in detalles:
        if detalle.valor_abono_euro:
            detalle.base_imponible = detalle.valor_abono_euro / Decimal(str(iva_factor))
        else:
            detalle.base_imponible = Decimal('0')
    
    # If iva_abono doesn't exist as a model field, calculate it
    if not hasattr(venta, 'iva_abono'):
        venta.total_base_imponible = venta.valor_total_abono_euro / Decimal(str(iva_factor))
        venta.iva_abono = venta.total_base_imponible * (iva_percentage / 100)
    
    # If valor_total_abono_euro_con_iva doesn't exist as a model field, calculate it
    if not hasattr(venta, 'valor_total_abono_euro_con_iva'):
        venta.valor_total_abono_euro_con_iva = venta.valor_total_abono_euro
        
    # Calculate the total number of boxes in the credit note
    if not hasattr(venta, 'total_cajas_abono') or venta.total_cajas_abono is None:
        venta.total_cajas_abono = sum(
            detalle.no_cajas_abono for detalle in detalles 
            if detalle.no_cajas_abono is not None
        )
        
    return render(request, 'ventas/rectificativa_cliente_token.html', {
        'venta': venta,
        'detalles': detalles,
        'token': token
    })
