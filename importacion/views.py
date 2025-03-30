from django.shortcuts import render
from django.http import JsonResponse
from .models import Bodega
from django.utils import timezone

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


