from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.urls import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import (
    TranferenciasExportador, TranferenciasAduana, TranferenciasCarga,
    Exportador, AgenciaAduana, AgenciaCarga, 
    BalanceExportador, BalanceGastosAduana, BalanceGastosCarga
)
from comercial.models import Cliente, TranferenciasCliente, BalanceCliente

def transferencias_view(request):
    """View to display all transfers in a tabbed interface with pagination"""
    # Get active tab from request or default to 'exportador'
    active_tab = request.GET.get('tab', 'exportador')
    
    # Get all data
    transferencias_exportador_list = TranferenciasExportador.objects.all().select_related('exportador').order_by('-id')
    transferencias_aduana_list = TranferenciasAduana.objects.all().select_related('agencia_aduana').order_by('-id')
    transferencias_carga_list = TranferenciasCarga.objects.all().select_related('agencia_carga').order_by('-id')
    transferencias_cliente_list = TranferenciasCliente.objects.all().select_related('cliente').order_by('-id')
    
    # Get balance data
    balances_exportador = BalanceExportador.objects.all().select_related('exportador')
    balances_aduana = BalanceGastosAduana.objects.all().select_related('agencia_aduana')
    balances_carga = BalanceGastosCarga.objects.all().select_related('agencia_carga')
    balances_cliente = BalanceCliente.objects.all().select_related('cliente')
    
    # Calculate totals for balance cards
    from decimal import Decimal
    total_balance_exportadores = sum(balance.saldo_disponible or Decimal('0') for balance in balances_exportador)
    total_balance_aduanas = sum(balance.saldo_disponible or Decimal('0') for balance in balances_aduana)
    total_balance_cargas = sum(balance.saldo_disponible or Decimal('0') for balance in balances_carga)
    total_balance_clientes = sum(balance.saldo_disponible or Decimal('0') for balance in balances_cliente)
    
    # Pagination for each tab
    page = request.GET.get('page', 1)
    items_per_page = 10  # Adjust as needed
    
    # Create paginators for each list
    paginator_exportador = Paginator(transferencias_exportador_list, items_per_page)
    paginator_aduana = Paginator(transferencias_aduana_list, items_per_page)
    paginator_carga = Paginator(transferencias_carga_list, items_per_page)
    paginator_cliente = Paginator(transferencias_cliente_list, items_per_page)
    
    # Get requested page for the active tab
    try:
        if active_tab == 'exportador':
            transferencias_exportador = paginator_exportador.page(page)
            is_paginated = paginator_exportador.num_pages > 1
        elif active_tab == 'aduana':
            transferencias_aduana = paginator_aduana.page(page)
            is_paginated = paginator_aduana.num_pages > 1
        elif active_tab == 'carga':
            transferencias_carga = paginator_carga.page(page)
            is_paginated = paginator_carga.num_pages > 1
        elif active_tab == 'cliente':
            transferencias_cliente = paginator_cliente.page(page)
            is_paginated = paginator_cliente.num_pages > 1
        else:
            active_tab = 'exportador'  # Default if invalid tab
            transferencias_exportador = paginator_exportador.page(page)
            is_paginated = paginator_exportador.num_pages > 1
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        if active_tab == 'exportador':
            transferencias_exportador = paginator_exportador.page(1)
            is_paginated = paginator_exportador.num_pages > 1
        elif active_tab == 'aduana':
            transferencias_aduana = paginator_aduana.page(1)
            is_paginated = paginator_aduana.num_pages > 1
        elif active_tab == 'carga':
            transferencias_carga = paginator_carga.page(1)
            is_paginated = paginator_carga.num_pages > 1
        elif active_tab == 'cliente':
            transferencias_cliente = paginator_cliente.page(1)
            is_paginated = paginator_cliente.num_pages > 1
    except EmptyPage:
        # If page is out of range, deliver last page of results
        if active_tab == 'exportador':
            transferencias_exportador = paginator_exportador.page(paginator_exportador.num_pages)
            is_paginated = paginator_exportador.num_pages > 1
        elif active_tab == 'aduana':
            transferencias_aduana = paginator_aduana.page(paginator_aduana.num_pages)
            is_paginated = paginator_aduana.num_pages > 1
        elif active_tab == 'carga':
            transferencias_carga = paginator_carga.page(paginator_carga.num_pages)
            is_paginated = paginator_carga.num_pages > 1
        elif active_tab == 'cliente':
            transferencias_cliente = paginator_cliente.page(paginator_cliente.num_pages)
            is_paginated = paginator_cliente.num_pages > 1
    
    # Set default empty values for non-active tabs
    if active_tab != 'exportador':
        transferencias_exportador = []
    if active_tab != 'aduana':
        transferencias_aduana = []
    if active_tab != 'carga':
        transferencias_carga = []
    if active_tab != 'cliente':
        transferencias_cliente = []
    
    # Get dropdown data
    exportadores = Exportador.objects.all()
    agencias_aduana = AgenciaAduana.objects.all()
    agencias_carga = AgenciaCarga.objects.all()
    clientes = Cliente.objects.all()
    
    context = {
        'transferencias_exportador': transferencias_exportador,
        'transferencias_aduana': transferencias_aduana,
        'transferencias_carga': transferencias_carga,
        'transferencias_cliente': transferencias_cliente,
        'exportadores': exportadores,
        'agencias_aduana': agencias_aduana,
        'agencias_carga': agencias_carga,
        'clientes': clientes,
        'active_tab': active_tab,
        'is_paginated': is_paginated,
        'page_obj': locals().get(f'transferencias_{active_tab}'),  # Get the appropriate page object
        # Balance data
        'balances_exportador': balances_exportador,
        'balances_aduana': balances_aduana,
        'balances_carga': balances_carga,
        'balances_cliente': balances_cliente,
        'total_balance_exportadores': total_balance_exportadores,
        'total_balance_aduanas': total_balance_aduanas,
        'total_balance_cargas': total_balance_cargas,
        'total_balance_clientes': total_balance_clientes,
    }
    
    return render(request, 'transferencias/transferencias.html', context)

# -------------------- Transferencias Exportador --------------------

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