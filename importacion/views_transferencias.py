from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from django_tables2 import SingleTableView
from django.utils.decorators import method_decorator

from .models import (
    TranferenciasExportador, TranferenciasAduana, TranferenciasCarga,
    Exportador, AgenciaAduana, AgenciaCarga,
    BalanceExportador, BalanceGastosAduana, BalanceGastosCarga
)
from comercial.models import Cliente, TranferenciasCliente, BalanceCliente
from .tables_transferencias import (
    TranferenciasExportadorTable, TranferenciasAduanaTable,
    TranferenciasCargaTable, TranferenciasClienteTable
)
from .filters import (
    TranferenciasExportadorFilter, TranferenciasAduanaFilter,
    TranferenciasCargaFilter, TranferenciasClienteFilter
)

@login_required
def transferencias_view(request):
    # This view now only shows the dashboard
    balances_exportador = BalanceExportador.objects.select_related('exportador').all()
    balances_aduana = BalanceGastosAduana.objects.select_related('agencia_aduana').all()
    balances_carga = BalanceGastosCarga.objects.select_related('agencia_carga').all()
    balances_cliente = BalanceCliente.objects.select_related('cliente').all()

    total_balance_exportadores = sum(b.saldo_disponible for b in balances_exportador)
    total_balance_aduanas = sum(b.saldo_disponible for b in balances_aduana)
    total_balance_cargas = sum(b.saldo_disponible for b in balances_carga)
    total_balance_clientes = sum(b.saldo_disponible for b in balances_cliente)

    context = {
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


@method_decorator(login_required, name='dispatch')
class BaseTransferenciaListView(SingleTableView):
    template_name = None
    table_class = None
    model = None
    filterset_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        self.filter = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.filter
        return context

class TransferenciasExportadorListView(BaseTransferenciaListView):
    model = TranferenciasExportador
    table_class = TranferenciasExportadorTable
    template_name = 'transferencias/transferencias_exportador_list.html'
    filterset_class = TranferenciasExportadorFilter

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['exportadores'] = Exportador.objects.all()
        return context

class TransferenciasAduanaListView(BaseTransferenciaListView):
    model = TranferenciasAduana
    table_class = TranferenciasAduanaTable
    template_name = 'transferencias/transferencias_aduana_list.html'
    filterset_class = TranferenciasAduanaFilter

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agencias_aduana'] = AgenciaAduana.objects.all()
        return context

class TransferenciasCargaListView(BaseTransferenciaListView):
    model = TranferenciasCarga
    table_class = TranferenciasCargaTable
    template_name = 'transferencias/transferencias_carga_list.html'
    filterset_class = TranferenciasCargaFilter

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agencias_carga'] = AgenciaCarga.objects.all()
        return context

class TransferenciasClienteListView(BaseTransferenciaListView):
    model = TranferenciasCliente
    table_class = TranferenciasClienteTable
    template_name = 'transferencias/transferencias_cliente_list.html'
    filterset_class = TranferenciasClienteFilter

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clientes'] = Cliente.objects.all()
        return context


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
    
    return redirect('importacion:transferencias_exportador_list')

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
    
    return redirect('importacion:transferencias_exportador_list')

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

    return redirect('importacion:transferencias_exportador_list')

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
    
    return redirect('importacion:transferencias_aduana_list')

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
    
    return redirect('importacion:transferencias_aduana_list')

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
    
    return redirect('importacion:transferencias_aduana_list')


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
    
    return redirect('importacion:transferencias_carga_list')

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
    
    return redirect('importacion:transferencias_carga_list')

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
    
    return redirect('importacion:transferencias_carga_list')

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
    
    return redirect('importacion:transferencias_cliente_list')

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
    
    return redirect('importacion:transferencias_cliente_list')

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
    
    return redirect('importacion:transferencias_cliente_list')

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
