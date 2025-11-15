import django_filters
from .models import TranferenciasExportador, TranferenciasAduana, TranferenciasCarga
from comercial.models import TranferenciasCliente

class TranferenciasExportadorFilter(django_filters.FilterSet):
    class Meta:
        model = TranferenciasExportador
        fields = ['exportador', 'referencia', 'fecha_transferencia']

class TranferenciasAduanaFilter(django_filters.FilterSet):
    class Meta:
        model = TranferenciasAduana
        fields = ['agencia_aduana', 'referencia', 'fecha_transferencia']

class TranferenciasCargaFilter(django_filters.FilterSet):
    class Meta:
        model = TranferenciasCarga
        fields = ['agencia_carga', 'referencia', 'fecha_transferencia']

class TranferenciasClienteFilter(django_filters.FilterSet):
    class Meta:
        model = TranferenciasCliente
        fields = ['cliente', 'referencia', 'fecha_transferencia']
