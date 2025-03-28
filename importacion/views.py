from django.shortcuts import render
from .models import Bodega

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


