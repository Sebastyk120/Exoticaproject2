from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.urls import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from datetime import datetime

from .models import (
    TranferenciasExportador, TranferenciasAduana, TranferenciasCarga,
    Exportador, AgenciaAduana, AgenciaCarga, 
    BalanceExportador, BalanceGastosAduana, BalanceGastosCarga
)
from comercial.models import Cliente, TranferenciasCliente, BalanceCliente

@login_required
def transferencias_view(request):
    # Obtener el tab activo
    active_tab = request.GET.get('tab', 'exportador')
    
    # Obtener filtros
    exportador_filter = request.GET.get('exportador_filter')
    aduana_filter = request.GET.get('aduana_filter')
    carga_filter = request.GET.get('carga_filter')
    cliente_filter = request.GET.get('cliente_filter')
    
    # Obtener todas las transferencias sin filtro de fecha
    transferencias_exportador = TranferenciasExportador.objects.all()
    transferencias_aduana = TranferenciasAduana.objects.all()
    transferencias_carga = TranferenciasCarga.objects.all()
    transferencias_cliente = TranferenciasCliente.objects.all()
    
    # Aplicar filtros según el tab activo
    if active_tab == 'exportador' and exportador_filter:
        transferencias_exportador = transferencias_exportador.filter(exportador_id=exportador_filter)
    elif active_tab == 'aduana' and aduana_filter:
        transferencias_aduana = transferencias_aduana.filter(agencia_aduana_id=aduana_filter)
    elif active_tab == 'carga' and carga_filter:
        transferencias_carga = transferencias_carga.filter(agencia_carga_id=carga_filter)
    elif active_tab == 'cliente' and cliente_filter:
        transferencias_cliente = transferencias_cliente.filter(cliente_id=cliente_filter)
    
    # Ordenar por fecha descendente
    transferencias_exportador = transferencias_exportador.order_by('-fecha_transferencia')
    transferencias_aduana = transferencias_aduana.order_by('-fecha_transferencia')
    transferencias_carga = transferencias_carga.order_by('-fecha_transferencia')
    transferencias_cliente = transferencias_cliente.order_by('-fecha_transferencia')
    
    # Paginación
    page_exportador = request.GET.get('page_exportador', 1)
    page_aduana = request.GET.get('page_aduana', 1)
    page_carga = request.GET.get('page_carga', 1)
    page_cliente = request.GET.get('page_cliente', 1)
    
    paginator = Paginator(transferencias_exportador, 10)
    try:
        transferencias_exportador = paginator.page(page_exportador)
    except PageNotAnInteger:
        transferencias_exportador = paginator.page(1)
    except EmptyPage:
        transferencias_exportador = paginator.page(paginator.num_pages)
    
    paginator = Paginator(transferencias_aduana, 10)
    try:
        transferencias_aduana = paginator.page(page_aduana)
    except PageNotAnInteger:
        transferencias_aduana = paginator.page(1)
    except EmptyPage:
        transferencias_aduana = paginator.page(paginator.num_pages)
    
    paginator = Paginator(transferencias_carga, 10)
    try:
        transferencias_carga = paginator.page(page_carga)
    except PageNotAnInteger:
        transferencias_carga = paginator.page(1)
    except EmptyPage:
        transferencias_carga = paginator.page(paginator.num_pages)
    
    paginator = Paginator(transferencias_cliente, 10)
    try:
        transferencias_cliente = paginator.page(page_cliente)
    except PageNotAnInteger:
        transferencias_cliente = paginator.page(1)
    except EmptyPage:
        transferencias_cliente = paginator.page(paginator.num_pages)
    
    # Obtener datos para los dropdowns
    exportadores = Exportador.objects.all()
    agencias_aduana = AgenciaAduana.objects.all()
    agencias_carga = AgenciaCarga.objects.all()
    clientes = Cliente.objects.all()
    
    # Obtener balances
    balances_exportador = BalanceExportador.objects.select_related('exportador').all()
    balances_aduana = BalanceGastosAduana.objects.select_related('agencia_aduana').all()
    balances_carga = BalanceGastosCarga.objects.select_related('agencia_carga').all()
    balances_cliente = BalanceCliente.objects.select_related('cliente').all()
    
    # Calcular totales de balances
    total_balance_exportadores = sum(b.saldo_disponible for b in balances_exportador)
    total_balance_aduanas = sum(b.saldo_disponible for b in balances_aduana)
    total_balance_cargas = sum(b.saldo_disponible for b in balances_carga)
    total_balance_clientes = sum(b.saldo_disponible for b in balances_cliente)
    
    context = {
        'active_tab': active_tab,
        'transferencias_exportador': transferencias_exportador,
        'transferencias_aduana': transferencias_aduana,
        'transferencias_carga': transferencias_carga,
        'transferencias_cliente': transferencias_cliente,
        'exportadores': exportadores,
        'agencias_aduana': agencias_aduana,
        'agencias_carga': agencias_carga,
        'clientes': clientes,
        'exportador_filter': exportador_filter,
        'aduana_filter': aduana_filter,
        'carga_filter': carga_filter,
        'cliente_filter': cliente_filter,
        'balances_exportador': balances_exportador,
        'balances_aduana': balances_aduana,
        'balances_carga': balances_carga,
        'balances_cliente': balances_cliente,
        'total_balance_exportadores': total_balance_exportadores,
        'total_balance_aduanas': total_balance_aduanas,
        'total_balance_cargas': total_balance_cargas,
        'total_balance_clientes': total_balance_clientes,
        'is_paginated': True,
        'page_obj': transferencias_exportador if active_tab == 'exportador' else 
                    transferencias_aduana if active_tab == 'aduana' else
                    transferencias_carga if active_tab == 'carga' else
                    transferencias_cliente
    }
    
    return render(request, 'transferencias/transferencias.html', context)

# -------------------- Transferencias Exportador --------------------

@login_required
@require_POST
def crear_transferencia_exportador(request):
    """Create a new TranferenciasExportador instance"""
    try:
        with transaction.atomic():
            exportador_id = request.POST.get('exportador')
            valor_transferencia = float(request.POST.get('valor_transferencia'))
            valor_transferencia_eur = float(request.POST.get('valor_transferencia_eur'))
            
            # Calculate TRM
            trm = None
            if valor_transferencia_eur > 0:
                trm = valor_transferencia / valor_transferencia_eur
            
            transferencia = TranferenciasExportador(
                exportador_id=exportador_id,
                referencia=request.POST.get('referencia'),
                fecha_transferencia=request.POST.get('fecha_transferencia'),
                valor_transferencia=valor_transferencia,
                valor_transferencia_eur=valor_transferencia_eur,
                trm=trm,
                concepto=request.POST.get('concepto')
            )
            transferencia.save()
            messages.success(request, 'Transferencia a exportador creada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al crear transferencia: {str(e)}')
    
    # Redirect to the correct tab
    return HttpResponseRedirect(reverse('importacion:transferencias') + '?tab=exportador')

@login_required
@require_POST
def editar_transferencia_exportador(request, pk):
    """Edit an existing TranferenciasExportador instance"""
    transferencia = get_object_or_404(TranferenciasExportador, pk=pk)
    try:
        with transaction.atomic():
            transferencia.exportador_id = request.POST.get('exportador')
            transferencia.referencia = request.POST.get('referencia')
            transferencia.fecha_transferencia = request.POST.get('fecha_transferencia')
            
            valor_transferencia = float(request.POST.get('valor_transferencia'))
            valor_transferencia_eur = float(request.POST.get('valor_transferencia_eur'))
            
            transferencia.valor_transferencia = valor_transferencia
            transferencia.valor_transferencia_eur = valor_transferencia_eur
            
            # Calculate TRM
            if valor_transferencia_eur > 0:
                transferencia.trm = valor_transferencia / valor_transferencia_eur
            
            transferencia.concepto = request.POST.get('concepto')
            transferencia.save()
            messages.success(request, 'Transferencia a exportador actualizada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al actualizar transferencia: {str(e)}')
    
    # Redirect to the correct tab
    return HttpResponseRedirect(reverse('importacion:transferencias') + '?tab=exportador')

@login_required
@require_POST
def eliminar_transferencia_exportador(request, pk):
    """Delete a TranferenciasExportador instance"""
    transferencia = get_object_or_404(TranferenciasExportador, pk=pk)
    try:
        transferencia.delete()
        messages.success(request, 'Transferencia a exportador eliminada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al eliminar transferencia: {str(e)}')
    
    # Redirect to the correct tab
    return HttpResponseRedirect(reverse('importacion:transferencias') + '?tab=exportador')

# -------------------- Transferencias Aduana --------------------

@login_required
@require_POST
def crear_transferencia_aduana(request):
    """Create a new TranferenciasAduana instance"""
    try:
        with transaction.atomic():
            agencia_aduana_id = request.POST.get('agencia_aduana')
            TranferenciasAduana.objects.create(
                agencia_aduana_id=agencia_aduana_id,
                referencia=request.POST.get('referencia'),
                fecha_transferencia=request.POST.get('fecha_transferencia'),
                valor_transferencia=request.POST.get('valor_transferencia'),
                concepto=request.POST.get('concepto')
            )
            messages.success(request, 'Transferencia a aduana creada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al crear transferencia: {str(e)}')
    
    # Use the explicit redirect with tab parameter instead of hash
    return HttpResponseRedirect(reverse('importacion:transferencias') + '?tab=aduana')

@login_required
@require_POST
def editar_transferencia_aduana(request, pk):
    """Edit an existing TranferenciasAduana instance"""
    transferencia = get_object_or_404(TranferenciasAduana, pk=pk)
    try:
        with transaction.atomic():
            transferencia.agencia_aduana_id = request.POST.get('agencia_aduana')
            transferencia.referencia = request.POST.get('referencia')
            transferencia.fecha_transferencia = request.POST.get('fecha_transferencia')
            transferencia.valor_transferencia = request.POST.get('valor_transferencia')
            transferencia.concepto = request.POST.get('concepto')
            transferencia.save()
            messages.success(request, 'Transferencia a aduana actualizada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al actualizar transferencia: {str(e)}')
    
    # Use the explicit redirect with tab parameter instead of hash
    return HttpResponseRedirect(reverse('importacion:transferencias') + '?tab=aduana')

@login_required
@require_POST
def eliminar_transferencia_aduana(request, pk):
    """Delete a TranferenciasAduana instance"""
    transferencia = get_object_or_404(TranferenciasAduana, pk=pk)
    try:
        transferencia.delete()
        messages.success(request, 'Transferencia a aduana eliminada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al eliminar transferencia: {str(e)}')
    
    # Use the explicit redirect with tab parameter instead of hash
    return HttpResponseRedirect(reverse('importacion:transferencias') + '?tab=aduana')

# -------------------- Transferencias Carga --------------------

@login_required
@require_POST
def crear_transferencia_carga(request):
    """Create a new TranferenciasCarga instance"""
    try:
        with transaction.atomic():
            agencia_carga_id = request.POST.get('agencia_carga')
            valor_transferencia = float(request.POST.get('valor_transferencia'))
            valor_transferencia_eur = float(request.POST.get('valor_transferencia_eur'))
            
            # Calculate TRM
            trm = None
            if valor_transferencia_eur > 0:
                trm = valor_transferencia / valor_transferencia_eur
            
            transferencia = TranferenciasCarga(
                agencia_carga_id=agencia_carga_id,
                referencia=request.POST.get('referencia'),
                fecha_transferencia=request.POST.get('fecha_transferencia'),
                valor_transferencia=valor_transferencia,
                valor_transferencia_eur=valor_transferencia_eur,
                trm=trm,
                concepto=request.POST.get('concepto')
            )
            transferencia.save()
            messages.success(request, 'Transferencia a agencia de carga creada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al crear transferencia: {str(e)}')
    
    # Use the explicit redirect with tab parameter instead of hash
    return HttpResponseRedirect(reverse('importacion:transferencias') + '?tab=carga')

@login_required
@require_POST
def editar_transferencia_carga(request, pk):
    """Edit an existing TranferenciasCarga instance"""
    transferencia = get_object_or_404(TranferenciasCarga, pk=pk)
    try:
        with transaction.atomic():
            transferencia.agencia_carga_id = request.POST.get('agencia_carga')
            transferencia.referencia = request.POST.get('referencia')
            transferencia.fecha_transferencia = request.POST.get('fecha_transferencia')
            
            valor_transferencia = float(request.POST.get('valor_transferencia'))
            valor_transferencia_eur = float(request.POST.get('valor_transferencia_eur'))
            
            transferencia.valor_transferencia = valor_transferencia
            transferencia.valor_transferencia_eur = valor_transferencia_eur
            
            # Calculate TRM
            if valor_transferencia_eur > 0:
                transferencia.trm = valor_transferencia / valor_transferencia_eur
            
            transferencia.concepto = request.POST.get('concepto')
            transferencia.save()
            messages.success(request, 'Transferencia a agencia de carga actualizada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al actualizar transferencia: {str(e)}')
    
    # Use the explicit redirect with tab parameter instead of hash
    return HttpResponseRedirect(reverse('importacion:transferencias') + '?tab=carga')

@login_required
@require_POST
def eliminar_transferencia_carga(request, pk):
    """Delete a TranferenciasCarga instance"""
    transferencia = get_object_or_404(TranferenciasCarga, pk=pk)
    try:
        transferencia.delete()
        messages.success(request, 'Transferencia a agencia de carga eliminada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al eliminar transferencia: {str(e)}')
    
    # Use the explicit redirect with tab parameter instead of hash
    return HttpResponseRedirect(reverse('importacion:transferencias') + '?tab=carga')

# -------------------- Transferencias Cliente --------------------

@login_required
@require_POST
def crear_transferencia_cliente(request):
    """Create a new TranferenciasCliente instance"""
    try:
        with transaction.atomic():
            cliente_id = request.POST.get('cliente')
            TranferenciasCliente.objects.create(
                cliente_id=cliente_id,
                referencia=request.POST.get('referencia'),
                fecha_transferencia=request.POST.get('fecha_transferencia'),
                valor_transferencia=request.POST.get('valor_transferencia'),
                concepto=request.POST.get('concepto')
            )
            messages.success(request, 'Transferencia de cliente creada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al crear transferencia: {str(e)}')
    
    # Use the explicit redirect with tab parameter
    return HttpResponseRedirect(reverse('importacion:transferencias') + '?tab=cliente')

@login_required
@require_POST
def editar_transferencia_cliente(request, pk):
    """Edit an existing TranferenciasCliente instance"""
    transferencia = get_object_or_404(TranferenciasCliente, pk=pk)
    try:
        with transaction.atomic():
            transferencia.cliente_id = request.POST.get('cliente')
            transferencia.referencia = request.POST.get('referencia')
            transferencia.fecha_transferencia = request.POST.get('fecha_transferencia')
            transferencia.valor_transferencia = request.POST.get('valor_transferencia')
            transferencia.concepto = request.POST.get('concepto')
            transferencia.save()
            messages.success(request, 'Transferencia de cliente actualizada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al actualizar transferencia: {str(e)}')
    
    # Use the explicit redirect with tab parameter
    return HttpResponseRedirect(reverse('importacion:transferencias') + '?tab=cliente')

@login_required
@require_POST
def eliminar_transferencia_cliente(request, pk):
    """Delete a TranferenciasCliente instance"""
    transferencia = get_object_or_404(TranferenciasCliente, pk=pk)
    try:
        transferencia.delete()
        messages.success(request, 'Transferencia de cliente eliminada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al eliminar transferencia: {str(e)}')
    
    # Use the explicit redirect with tab parameter
    return HttpResponseRedirect(reverse('importacion:transferencias') + '?tab=cliente')

@login_required
def get_balances_data(request):
    """API endpoint to get all balance data in JSON format"""
    # Get all balances
    balances_exportador = BalanceExportador.objects.select_related('exportador').all()
    balances_aduana = BalanceGastosAduana.objects.select_related('agencia_aduana').all()
    balances_carga = BalanceGastosCarga.objects.select_related('agencia_carga').all()
    balances_cliente = BalanceCliente.objects.select_related('cliente').all()
    
    # Calculate totals
    total_exportadores = sum(b.saldo_disponible for b in balances_exportador)
    total_aduanas = sum(b.saldo_disponible for b in balances_aduana)
    total_cargas = sum(b.saldo_disponible for b in balances_carga)
    total_clientes = sum(b.saldo_disponible for b in balances_cliente)
    
    # Format data for JSON
    data = {
        'total_exportadores': f"${total_exportadores:,.2f}",
        'total_aduanas': f"€{total_aduanas:,.2f}",
        'total_cargas': f"${total_cargas:,.2f}",
        'total_clientes': f"€{total_clientes:,.2f}",
        'balances_exportador': [
            {
                'exportador': b.exportador.nombre,
                'saldo_disponible': f"${b.saldo_disponible:,.2f}",
                'ultima_actualizacion': b.ultima_actualizacion.strftime('%d/%m/%Y %H:%M'),
                'valor_usd': b.valor_transferencia if hasattr(b, 'valor_transferencia') else None,
                'valor_eur': b.valor_transferencia_eur if hasattr(b, 'valor_transferencia_eur') else None
            } for b in balances_exportador
        ],
        'balances_aduana': [
            {
                'agencia_aduana': b.agencia_aduana.nombre,
                'saldo_disponible': f"€{b.saldo_disponible:,.2f}",
                'ultima_actualizacion': b.ultima_actualizacion.strftime('%d/%m/%Y %H:%M')
            } for b in balances_aduana
        ],
        'balances_carga': [
            {
                'agencia_carga': b.agencia_carga.nombre,
                'saldo_disponible': f"${b.saldo_disponible:,.2f}",
                'ultima_actualizacion': b.ultima_actualizacion.strftime('%d/%m/%Y %H:%M'),
                'valor_usd': b.valor_transferencia if hasattr(b, 'valor_transferencia') else None,
                'valor_eur': b.valor_transferencia_eur if hasattr(b, 'valor_transferencia_eur') else None
            } for b in balances_carga
        ],
        'balances_cliente': [
            {
                'cliente': b.cliente.nombre,
                'saldo_disponible': f"€{b.saldo_disponible:,.2f}",
                'ultima_actualizacion': b.ultima_actualizacion.strftime('%d/%m/%Y %H:%M')
            } for b in balances_cliente
        ],
    }
    
    return JsonResponse(data)