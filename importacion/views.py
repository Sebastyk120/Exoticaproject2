from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import Bodega, Pedido
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.decorators import login_required

# Create your views here.

def bodega_view(request):
    """
    View to display the warehouse inventory.
    """
    bodegas = Bodega.objects.select_related('presentacion', 'presentacion__fruta').all()
    context = {
        'bodegas': bodegas,
    }
    return render(request, 'bodega/bodega.html', context)

def bodega_json(request):
    """
    API endpoint to get warehouse inventory data in JSON format.
    """
    bodegas = Bodega.objects.select_related('presentacion', 'presentacion__fruta').all()
    
    bodegas_data = []
    for bodega in bodegas:
        bodega_data = {
            'id': bodega.id,
            'stock_actual': bodega.stock_actual,
            'ultima_actualizacion': bodega.ultima_actualizacion.strftime('%d/%m/%Y %H:%M') if bodega.ultima_actualizacion else None,
            'presentacion': {
                'id': bodega.presentacion.id,
                'nombre': str(bodega.presentacion),
                'kilos': bodega.presentacion.kilos,
                'fruta': str(bodega.presentacion.fruta) if bodega.presentacion.fruta else None
            }
        }
        bodegas_data.append(bodega_data)
    
    return JsonResponse({
        'bodegas': bodegas_data
    })

@login_required
def eliminar_pedido(request, pedido_id):
    """Elimina un pedido si no tiene productos vendidos"""
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    
    try:
        with transaction.atomic():
            pedido.delete()
        messages.success(request, f'Pedido #{pedido_id} eliminado correctamente.')
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Error al eliminar el pedido: {str(e)}')
    
    return redirect('importacion:lista_pedidos')


