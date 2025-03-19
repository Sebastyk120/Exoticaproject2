from import_export import resources
from .models import Fruta, Presentacion, ListaPreciosImportacion, ListaPreciosVentas

class FrutaResource(resources.ModelResource):
    class Meta:
        model = Fruta
        fields = ('id', 'nombre')

class PresentacionResource(resources.ModelResource):
    class Meta:
        model = Presentacion
        fields = ('id', 'fruta', 'kilos')

class ListaPreciosImportacionResource(resources.ModelResource):
    class Meta:
        model = ListaPreciosImportacion
        fields = ('id', 'presentacion', 'precio_usd', 'exportador', 'fecha')

class ListaPreciosVentasResource(resources.ModelResource):
    class Meta:
        model = ListaPreciosVentas
        fields = ('id', 'presentacion', 'precio_euro', 'cliente', 'fecha')
