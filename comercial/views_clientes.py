from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import TruncMonth
from .models import Cliente, Venta, BalanceCliente, TranferenciasCliente, DetalleVenta
from decimal import Decimal
import json
from datetime import datetime, timedelta, date
import logging

# Set up logger
logger = logging.getLogger(__name__)

def clientes_view(request):
    clientes = Cliente.objects.all().order_by('nombre')
    return render(request, 'clientes/clientes.html', {'clientes': clientes})

def add_client(request):
    if request.method == 'POST':
        try:
            # Validar campos requeridos
            required_fields = ['nombre', 'email', 'domicilio', 'dias_pago']
            for field in required_fields:
                if not request.POST.get(field):
                    raise ValidationError(f'El campo {field} es requerido')

            # Crear el cliente
            cliente = Cliente.objects.create(
                nombre=request.POST['nombre'],
                ciudad=request.POST.get('ciudad', ''),
                email=request.POST['email'],
                email2=request.POST.get('email2', ''),
                telefono=request.POST.get('telefono', ''),
                dias_pago=request.POST['dias_pago'],
                domicilio=request.POST['domicilio'],
                cif=request.POST.get('cif', '')
            )
            messages.success(request, 'Cliente agregado exitosamente')
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error al agregar el cliente: {str(e)}')
    return redirect('comercial:clientes')

def get_client(request, client_id):
    try:
        cliente = get_object_or_404(Cliente, id=client_id)
        data = {
            'id': cliente.id,
            'nombre': cliente.nombre,
            'ciudad': cliente.ciudad,
            'email': cliente.email,
            'email2': cliente.email2,
            'telefono': cliente.telefono,
            'dias_pago': cliente.dias_pago,
            'domicilio': cliente.domicilio,
            'cif': cliente.cif
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def edit_client(request, client_id):
    if request.method == 'POST':
        try:
            cliente = get_object_or_404(Cliente, id=client_id)
            
            # Validar campos requeridos
            required_fields = ['nombre', 'email', 'domicilio', 'dias_pago']
            for field in required_fields:
                if not request.POST.get(field):
                    raise ValidationError(f'El campo {field} es requerido')

            # Actualizar el cliente
            cliente.nombre = request.POST['nombre']
            cliente.ciudad = request.POST.get('ciudad', '')
            cliente.email = request.POST['email']
            cliente.email2 = request.POST.get('email2', '')
            cliente.telefono = request.POST.get('telefono', '')
            cliente.dias_pago = request.POST['dias_pago']
            cliente.domicilio = request.POST['domicilio']
            cliente.cif = request.POST.get('cif', '')
            
            cliente.save()
            messages.success(request, 'Cliente actualizado exitosamente')
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error al actualizar el cliente: {str(e)}')
    return redirect('comercial:clientes')

def estado_cuenta_cliente(request, cliente_id):
    # Get all clients for the selector
    clientes = Cliente.objects.all().order_by('nombre')
    
    # Default to no client if ID is 0
    if cliente_id == 0:
        # If a client was selected via the form, redirect to their page
        if request.GET.get('cliente_id'):
            return redirect('comercial:estado_cuenta_cliente', cliente_id=request.GET.get('cliente_id'))
        return render(request, 'clientes/estado_cuenta_cliente.html', {'clientes': clientes})
    
    # Get the requested client
    cliente = get_object_or_404(Cliente, id=cliente_id)
    
    # Debug output to check incoming parameters
    logger.debug(f"Filter params - fecha_inicio: {request.GET.get('fecha_inicio')}, fecha_fin: {request.GET.get('fecha_fin')}")
    
    # Process date filters
    fecha_inicio = None
    fecha_fin = None
    
    # Check for fecha_inicio parameter and convert it to date object
    fecha_inicio_param = request.GET.get('fecha_inicio')
    if fecha_inicio_param and fecha_inicio_param.strip():
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_param, '%Y-%m-%d').date()
            logger.debug(f"Parsed fecha_inicio: {fecha_inicio}")
        except ValueError as e:
            logger.error(f"Error parsing fecha_inicio: {e}")
            messages.error(request, "Formato de fecha inicial inválido. Use YYYY-MM-DD.")
    
    # Check for fecha_fin parameter and convert it to date object
    fecha_fin_param = request.GET.get('fecha_fin')
    if fecha_fin_param and fecha_fin_param.strip():
        try:
            fecha_fin = datetime.strptime(fecha_fin_param, '%Y-%m-%d').date()
            logger.debug(f"Parsed fecha_fin: {fecha_fin}")
        except ValueError as e:
            logger.error(f"Error parsing fecha_fin: {e}")
            messages.error(request, "Formato de fecha final inválido. Use YYYY-MM-DD.")
    
    # Initial queries without date filters
    ventas_query = Venta.objects.filter(cliente=cliente)
    transferencias_query = TranferenciasCliente.objects.filter(cliente=cliente)
    
    # Log the initial query count
    total_ventas_inicial = ventas_query.count()
    total_transferencias_inicial = transferencias_query.count()
    logger.debug(f"Conteo inicial - Ventas: {total_ventas_inicial}, Transferencias: {total_transferencias_inicial}")
    
    # Apply date filters to venta query if provided
    if fecha_inicio:
        ventas_query = ventas_query.filter(fecha_entrega__gte=fecha_inicio)
        transferencias_query = transferencias_query.filter(fecha_transferencia__gte=fecha_inicio)
        logger.debug(f"Aplicando filtro fecha_inicio: {fecha_inicio}")
    
    if fecha_fin:
        ventas_query = ventas_query.filter(fecha_entrega__lte=fecha_fin)
        transferencias_query = transferencias_query.filter(fecha_transferencia__lte=fecha_fin)
        logger.debug(f"Aplicando filtro fecha_fin: {fecha_fin}")
    
    # Log the filtered query count
    total_ventas_filtradas = ventas_query.count()
    total_transferencias_filtradas = transferencias_query.count()
    logger.debug(f"Conteo filtrado - Ventas: {total_ventas_filtradas}, Transferencias: {total_transferencias_filtradas}")
    
    # Now filter detalles_query based on the already filtered ventas_query
    detalles_query = DetalleVenta.objects.filter(venta__in=ventas_query)
    
    # Get sales transactions ordered by date
    ventas = ventas_query.order_by('-fecha_entrega')
    
    # Get latest transfers ordered by date
    transferencias = transferencias_query.order_by('-fecha_transferencia')
    
    # Get client balance if exists
    try:
        balance = BalanceCliente.objects.get(cliente=cliente)
    except BalanceCliente.DoesNotExist:
        balance = None
    
    # Calculate summary metrics using the filtered queries
    total_facturado = ventas_query.aggregate(total=Sum('valor_total_factura_euro'))['total'] or 0
    total_cajas_vendidas = ventas_query.aggregate(total=Sum('total_cajas_pedido'))['total'] or 0
    total_reclamaciones = ventas_query.aggregate(total=Sum('valor_total_abono_euro'))['total'] or 0
    total_cajas_reclamadas = detalles_query.aggregate(total=Sum('no_cajas_abono'))['total'] or 0
    total_pagado_transferencias = transferencias_query.aggregate(total=Sum('valor_transferencia'))['total'] or 0
    
    # Calculate real balance for the filtered period
    saldo_real = total_facturado - total_reclamaciones - total_pagado_transferencias
    
    # Prepare data for transaction history chart (monthly aggregation)
    ventas_por_mes = ventas_query.annotate(
        mes=TruncMonth('fecha_entrega')
    ).values('mes').annotate(
        total_facturado=Sum('valor_total_factura_euro')
    ).order_by('mes')
    
    transferencias_por_mes = transferencias_query.annotate(
        mes=TruncMonth('fecha_transferencia')
    ).values('mes').annotate(
        total_pagado=Sum('valor_transferencia')
    ).order_by('mes')
    
    # Create dictionaries for easy lookup
    facturado_dict = {item['mes'].strftime('%Y-%m'): float(item['total_facturado']) for item in ventas_por_mes}
    pagado_dict = {item['mes'].strftime('%Y-%m'): float(item['total_pagado']) for item in transferencias_por_mes}
    
    # Combine all unique months
    all_months = sorted(set(list(facturado_dict.keys()) + list(pagado_dict.keys())))
    
    # Prepare final data for the chart
    fechas = all_months
    totales_facturados = [facturado_dict.get(month, 0) for month in all_months]
    totales_pagados = [pagado_dict.get(month, 0) for month in all_months]
    
    # Calculate payment status totals (count of paid vs unpaid invoices) from filtered ventas
    total_pagado = float(ventas_query.filter(pagado=True).count())
    total_pendiente = float(ventas_query.filter(pagado=False).count())
    
    # Calculate percentages for Estado de Cartera chart
    monto_pagado = ventas_query.filter(pagado=True).aggregate(total=Sum('valor_total_factura_euro'))['total'] or 0
    monto_pendiente = total_facturado - monto_pagado - total_reclamaciones
    
    # Ensure we don't divide by zero
    if total_facturado > 0:
        porcentaje_pagado = (monto_pagado / total_facturado) * 100
        porcentaje_reclamaciones = (total_reclamaciones / total_facturado) * 100
        porcentaje_pendiente = (monto_pendiente / total_facturado) * 100
    else:
        porcentaje_pagado = porcentaje_reclamaciones = porcentaje_pendiente = 0
    
    # Calculate facturas proximas a vencer
    hoy = date.today()
    # Get ventas not paid yet
    facturas_pendientes = ventas_query.filter(pagado=False).order_by('fecha_entrega')
    
    # Calculate dias_vencimiento for each factura based on dias_pago from cliente
    facturas_con_vencimiento = []
    for factura in facturas_pendientes:
        # Calculate expected payment date (fecha_entrega + dias_pago)
        if factura.fecha_entrega and cliente.dias_pago:
            try:
                dias_pago = int(cliente.dias_pago)
                fecha_vencimiento = factura.fecha_entrega + timedelta(days=dias_pago)
                dias_hasta_vencimiento = (fecha_vencimiento - hoy).days
                
                # Add status based on days until expiration
                estado = "vencida" if dias_hasta_vencimiento < 0 else "proxima" if dias_hasta_vencimiento <= 7 else "normal"
                
                facturas_con_vencimiento.append({
                    'factura': factura,
                    'fecha_vencimiento': fecha_vencimiento,
                    'dias_hasta_vencimiento': dias_hasta_vencimiento,
                    'estado': estado
                })
            except (ValueError, TypeError):
                # If dias_pago is not a valid integer
                facturas_con_vencimiento.append({
                    'factura': factura,
                    'fecha_vencimiento': None,
                    'dias_hasta_vencimiento': None,
                    'estado': "desconocido"
                })
    
    # Sort by expiration date (most urgent first)
    facturas_con_vencimiento = sorted(facturas_con_vencimiento, key=lambda x: x['dias_hasta_vencimiento'] if x['dias_hasta_vencimiento'] is not None else 999)
    
    context = {
        'clientes': clientes,
        'cliente': cliente,
        'ventas': ventas,
        'transferencias': transferencias,
        'balance': balance,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        # Summary data
        'total_facturado': total_facturado,
        'total_cajas_vendidas': total_cajas_vendidas,
        'total_reclamaciones': total_reclamaciones,
        'total_cajas_reclamadas': total_cajas_reclamadas,
        'total_pagado_transferencias': total_pagado_transferencias,
        'saldo_real': saldo_real,
        # Chart data
        'fechas': json.dumps(fechas),
        'totales_facturados': json.dumps(totales_facturados),
        'totales_pagados': json.dumps(totales_pagados),
        'total_pagado': json.dumps(total_pagado),
        'total_pendiente': json.dumps(total_pendiente),
        # Estado de Cartera percentages
        'porcentaje_pagado': json.dumps(float(porcentaje_pagado)),
        'porcentaje_reclamaciones': json.dumps(float(porcentaje_reclamaciones)),
        'porcentaje_pendiente': json.dumps(float(porcentaje_pendiente)),
        # Facturas proximas a vencer
        'facturas_con_vencimiento': facturas_con_vencimiento,
        # Debug data
        'tiene_filtros': bool(fecha_inicio or fecha_fin),
        'debug_total_ventas_inicial': total_ventas_inicial,
        'debug_total_ventas_filtradas': total_ventas_filtradas,
        'debug_total_transferencias_inicial': total_transferencias_inicial,
        'debug_total_transferencias_filtradas': total_transferencias_filtradas,
    }
    
    return render(request, 'clientes/estado_cuenta_cliente.html', context)
