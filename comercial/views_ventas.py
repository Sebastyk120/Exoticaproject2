import decimal
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date
from decimal import Decimal
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.conf import settings
from .models import Venta, DetalleVenta, Cliente, BalanceCliente, TranferenciasCliente
from productos.models import Presentacion, ListaPreciosVentas
from django.utils import timezone
from django.core.exceptions import ValidationError
from importacion.models import Bodega, Pedido

@login_required
def lista_ventas(request):
    """View to list all sales with search and filter functionality"""
    queryset = Venta.objects.all().select_related('cliente').prefetch_related('pedidos')
    
    search_query = request.GET.get('q', '')
    if search_query:
        queryset = queryset.filter(
            Q(numero_factura__icontains=search_query) |
            Q(cliente__nombre__icontains=search_query) |
            Q(semana__icontains=search_query)
        )
    
    pagado_filter = request.GET.get('pagado', '')
    if pagado_filter:
        pagado_bool = pagado_filter == 'Si'
        queryset = queryset.filter(pagado=pagado_bool)
    
    queryset = queryset.order_by('-id')
    
    paginator = Paginator(queryset, 10)
    page = request.GET.get('page')
    
    try:
        ventas = paginator.page(page)
    except PageNotAnInteger:
        ventas = paginator.page(1)
    except EmptyPage:
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
        detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
        
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
    
    clientes = Cliente.objects.all()
    presentaciones = Presentacion.objects.all().select_related('fruta')
    
    if venta:
        pedidos_asignados = venta.pedidos.all()
        ultimos_pedidos = Pedido.objects.exclude(id__in=pedidos_asignados).order_by('-fecha_entrega')[:5]
        todos_pedidos = list(pedidos_asignados) + list(ultimos_pedidos)
        todos_pedidos = list(dict.fromkeys(todos_pedidos))
    else:
        todos_pedidos = Pedido.objects.all().order_by('-fecha_entrega')[:5]
    
    context = {
        'venta': venta,
        'detalles': detalles,
        'clientes': clientes,
        'presentaciones': presentaciones,
        'ultimos_pedidos': todos_pedidos,
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
        
        cliente_id = request.POST.get('cliente')
        if not cliente_id:
            return JsonResponse({'success': False, 'message': 'Debe seleccionar un cliente.'}, status=400)
        
        try:
            cliente = Cliente.objects.get(id=cliente_id)
            venta.cliente = cliente
        except Cliente.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'El cliente seleccionado no existe.'}, status=400)
        
        pedidos_seleccionados = request.POST.getlist('pedidos')
        if not pedidos_seleccionados:
            return JsonResponse({'success': False, 'message': 'Debe seleccionar al menos un pedido.'}, status=400)
        
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
        
        try:
            primer_pedido = Pedido.objects.get(id=pedidos_seleccionados[0])
            venta.fecha_compra = primer_pedido.fecha_entrega
            venta.semana = primer_pedido.semana
        except Pedido.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Uno de los pedidos seleccionados no existe.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error al procesar el pedido: {str(e)}'}, status=400)
        
        try:
            iva_str = request.POST.get('porcentaje_iva', '4.00')
            venta.porcentaje_iva = Decimal(iva_str)
        except (ValueError, decimal.InvalidOperation):
            venta.porcentaje_iva = Decimal('4.00')
        
        # El numero_nc se genera automáticamente en el modelo cuando hay cajas de abono
        venta.observaciones = request.POST.get('observaciones', '')
        venta.origen = request.POST.get('origen', '')
        
        venta.save()
        
        venta.pedidos.set(pedidos_seleccionados)
        
        pedidos_actuales = venta.pedidos.all()
        if pedidos_actuales.exists():
            primer_pedido = pedidos_actuales.first()
            if primer_pedido and primer_pedido.semana:
                venta.semana = primer_pedido.semana
                venta.save(update_fields=['semana'])
        
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
    
    try:
        detalle.presentacion_id = request.POST.get('presentacion')
        detalle.cajas_enviadas = int(request.POST.get('cajas_enviadas') or 0)
        valor_caja = Decimal(request.POST.get('valor_x_caja_euro') or 0)
        
        if valor_caja <= 0:
            messages.error(request, 'El valor de la caja debe ser mayor que 0.')
            return redirect('comercial:detalle_venta', venta_id=venta.id)
            
        detalle.valor_x_caja_euro = valor_caja
        detalle.no_cajas_abono = Decimal(request.POST.get('no_cajas_abono') or 0)
    except (ValueError, TypeError, decimal.InvalidOperation):
        messages.error(request, 'Error al procesar algunos valores numéricos. Por favor, verifique los datos.')
        return redirect('comercial:detalle_venta', venta_id=venta.id)
    
    detalle.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'detalle_id': detalle.id})
    
    messages.success(request, 'Detalle de venta guardado correctamente')
    return redirect('comercial:detalle_venta', venta_id=venta.id)

@login_required
@require_POST
def guardar_detalles_batch(request, venta_id):
    """Handle saving multiple sale details at once"""
    venta = get_object_or_404(Venta, pk=venta_id)
    
    delete_ids = request.POST.getlist('delete_detail_ids')
    if delete_ids:
        DetalleVenta.objects.filter(id__in=delete_ids, venta=venta).delete()
    
    form_keys = request.POST.keys()
    
    existing_pattern = r'detalle_(\d+)_(\w+)'
    existing_ids = set()
    import re
    
    for key in form_keys:
        match = re.match(existing_pattern, key)
        if match:
            existing_ids.add(match.group(1))
    
    for detail_id in existing_ids:
        try:
            detalle = DetalleVenta.objects.get(pk=detail_id, venta=venta)
            
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
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, f'Error en detalle #{detail_id}: {error}')
            return redirect('comercial:detalle_venta', venta_id=venta.id)
        except (DetalleVenta.DoesNotExist, ValueError, TypeError, decimal.InvalidOperation) as e:
            messages.error(request, f'Error al actualizar detalle #{detail_id}: {str(e)}')
            return redirect('comercial:detalle_venta', venta_id=venta.id)
    
    new_pattern = r'new_(\d+)_(\w+)'
    new_indices = set()
    
    for key in form_keys:
        match = re.match(new_pattern, key)
        if match:
            new_indices.add(match.group(1))
    
    for index in new_indices:
        try:
            presentacion_id = request.POST.get(f'new_{index}_presentacion')
            if not presentacion_id:
                continue
                
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
    todos_pedidos = Pedido.objects.all().order_by('-fecha_entrega')[:5]
    
    context = {
        'venta': None,
        'detalles': [],
        'clientes': Cliente.objects.all(),
        'presentaciones': Presentacion.objects.all().select_related('fruta'),
        'ultimos_pedidos': todos_pedidos,
    }
    return render(request, 'ventas/ventas.html', context)

@login_required
def obtener_detalles_venta(request, venta_id):
    """Vista para obtener los detalles de una venta en formato JSON para el modal"""
    venta = get_object_or_404(Venta, pk=venta_id)
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
    
    venta_data = {
        'id': venta.id,
        'cliente': venta.cliente.nombre,
        'fecha_entrega': venta.fecha_entrega.strftime('%d/%m/%Y'),
        'fecha_vencimiento': venta.fecha_vencimiento.strftime('%d/%m/%Y') if venta.fecha_vencimiento else '-',
        'total_cajas': f"{venta.total_cajas_pedido or 0}",
        'total_euros': f"€{venta.valor_total_factura_euro or 0:.2f}"
    }
    
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
    try:
        presentacion_id = int(presentacion_id)
        cliente_id = int(cliente_id)
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'IDs de presentación o cliente inválidos'
        }, status=400)
    
    try:
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
        
        precio = ListaPreciosVentas.objects.filter(
            presentacion_id=presentacion_id,
            cliente_id=cliente_id
        ).first()
        
        if precio:
            return JsonResponse({
                'success': True,
                'precio': float(precio.precio_euro)
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'No hay precio configurado para esta presentación y cliente'
            }, status=404)
    except Exception as e:
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
    
    if not venta.numero_nc:
        messages.error(request, "Esta venta no tiene una factura rectificativa asociada.")
        return redirect('comercial:generar_factura', venta_id=venta_id)
    
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
    
    iva_percentage = venta.porcentaje_iva
    iva_factor = 1 + (iva_percentage / 100)
    
    for detalle in detalles:
        if detalle.valor_abono_euro:
            detalle.base_imponible = detalle.valor_abono_euro / Decimal(str(iva_factor))
        else:
            detalle.base_imponible = Decimal('0')
    
    if not hasattr(venta, 'iva_abono'):
        venta.total_base_imponible = venta.valor_total_abono_euro / Decimal(str(iva_factor))
        venta.iva_abono = venta.total_base_imponible * (iva_percentage / 100)
    
    if not hasattr(venta, 'valor_total_abono_euro_con_iva'):
        venta.valor_total_abono_euro_con_iva = venta.valor_total_abono_euro
        
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
        presentacion = Presentacion.objects.get(id=presentacion_id)
        
        bodega = Bodega.objects.get(presentacion=presentacion)
        stock_disponible = bodega.stock_actual
        
        if detalle_id:
            try:
                detalle_existente = DetalleVenta.objects.get(id=detalle_id)
                stock_disponible += detalle_existente.cajas_enviadas
            except DetalleVenta.DoesNotExist:
                pass
        
        if stock_disponible < cajas_enviadas:
            return JsonResponse({
                'success': False,
                'message': f'Stock insuficiente. Solo hay {stock_disponible} cajas disponibles de {presentacion.fruta.nombre} - {presentacion.kilos} Kg',
                'stock_disponible': stock_disponible
            })
        
        return JsonResponse({
            'success': True,
            'message': 'Stock suficiente',
            'stock_disponible': stock_disponible
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
    cliente = get_object_or_404(Cliente, token_acceso=token)
    
    venta = get_object_or_404(Venta, pk=venta_id, cliente=cliente)
    
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
    
    return render(request, 'ventas/factura_cliente_token.html', {
        'venta': venta,
        'detalles': detalles,
        'token': token
    })

def rectificativa_cliente_token(request, venta_id, token):
    """Vista para que clientes puedan ver y descargar facturas rectificativas mediante token"""
    cliente = get_object_or_404(Cliente, token_acceso=token)
    
    venta = get_object_or_404(Venta, pk=venta_id, cliente=cliente)
    
    if not venta.numero_nc:
        messages.error(request, "Esta venta no tiene una factura rectificativa asociada.")
        return redirect('comercial:factura_cliente_token', venta_id=venta_id, token=token)
    
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('presentacion', 'presentacion__fruta')
    
    iva_percentage = venta.porcentaje_iva
    iva_factor = 1 + (iva_percentage / 100)
    
    for detalle in detalles:
        if detalle.valor_abono_euro:
            detalle.base_imponible = detalle.valor_abono_euro / Decimal(str(iva_factor))
        else:
            detalle.base_imponible = Decimal('0')
    
    if not hasattr(venta, 'iva_abono'):
        venta.total_base_imponible = venta.valor_total_abono_euro / Decimal(str(iva_factor))
        venta.iva_abono = venta.total_base_imponible * (iva_percentage / 100)
    
    if not hasattr(venta, 'valor_total_abono_euro_con_iva'):
        venta.valor_total_abono_euro_con_iva = venta.valor_total_abono_euro
        
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

@login_required
@require_POST
def registrar_pago_venta(request, venta_id):
    """Vista para registrar o actualizar un pago de transferencia desde una venta"""
    try:
        venta = get_object_or_404(Venta, pk=venta_id)
        
        # Validar que exista número de factura
        if not venta.numero_factura:
            return JsonResponse({
                'success': False,
                'message': 'La venta debe tener un número de factura asignado'
            }, status=400)
        
        # Obtener datos del formulario
        fecha_transferencia_str = request.POST.get('fecha_transferencia')
        valor_transferencia = request.POST.get('valor_transferencia')
        concepto = request.POST.get('concepto', '')
        
        # Validar datos requeridos
        if not fecha_transferencia_str or not valor_transferencia:
            return JsonResponse({
                'success': False,
                'message': 'Fecha y valor de transferencia son requeridos'
            }, status=400)
        
        # Parsear fecha
        try:
            fecha_transferencia = parse_date(fecha_transferencia_str)
            if not fecha_transferencia:
                raise ValueError('Fecha inválida')
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'message': 'La fecha de transferencia no es válida (formato: YYYY-MM-DD)'
            }, status=400)
        
        # Validar que la fecha no sea futura
        if fecha_transferencia > timezone.now().date():
            return JsonResponse({
                'success': False,
                'message': 'La fecha de transferencia no puede ser futura'
            }, status=400)
        
        # Validar valor
        try:
            valor_transferencia = Decimal(valor_transferencia)
            if valor_transferencia <= 0:
                raise ValueError('El valor debe ser mayor que 0')
        except (ValueError, decimal.InvalidOperation):
            return JsonResponse({
                'success': False,
                'message': 'El valor de la transferencia no es válido'
            }, status=400)
        
        # Validar que el monto no exceda lo adeudado
        monto_adeudado = venta.monto_pendiente or Decimal('0')
        if valor_transferencia > monto_adeudado:
            return JsonResponse({
                'success': False,
                'message': f'El monto de transferencia (€{valor_transferencia:.2f}) no puede exceder lo adeudado (€{monto_adeudado:.2f})'
            }, status=400)
        
        # Buscar si ya existe una transferencia con esta referencia
        referencia = venta.numero_factura
        
        # Usar get_or_create para evitar condiciones de carrera
        from django.db import transaction
        with transaction.atomic():
            transferencia, created = TranferenciasCliente.objects.get_or_create(
                cliente=venta.cliente,
                referencia=referencia,
                defaults={
                    'fecha_transferencia': fecha_transferencia,
                    'valor_transferencia': valor_transferencia,
                    'concepto': concepto
                }
            )
            
            # Si ya existía, actualizar los valores
            if not created:
                transferencia.fecha_transferencia = fecha_transferencia
                transferencia.valor_transferencia = valor_transferencia
                transferencia.concepto = concepto
                transferencia.save()
        
        # Actualizar venta con datos frescos
        venta.refresh_from_db()
        
        action = 'actualizado' if not created else 'registrado'
        message = f'Pago {action} correctamente para la factura {referencia}'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'venta_id': venta.id
        })
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error al registrar pago: {str(e)}', exc_info=True)
        
        return JsonResponse({
            'success': False,
            'message': f'Error al registrar el pago: {str(e)}'
        }, status=500)