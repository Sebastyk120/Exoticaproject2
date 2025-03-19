from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from import_export.admin import ImportExportModelAdmin
from .models import Fruta, Presentacion, ListaPreciosImportacion, ListaPreciosVentas
from .resources import (
    FrutaResource, PresentacionResource, ListaPreciosImportacionResource, ListaPreciosVentasResource
)
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm

@admin.register(Fruta)
class FrutaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('nombre',)
    search_fields = ('nombre',)
    search_help_text = "Buscar por: nombre."
    resource_class = FrutaResource

@admin.register(Presentacion)
class PresentacionAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('fruta', 'kilos')
    search_fields = ('fruta__nombre',)
    search_help_text = "Buscar por: nombre de la fruta."
    list_filter = ('fruta',)
    resource_class = PresentacionResource

@admin.register(ListaPreciosImportacion)
class ListaPreciosImportacionAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('presentacion', 'precio_usd', 'exportador', 'fecha')
    search_fields = ('presentacion__fruta__nombre', 'exportador__nombre')
    search_help_text = "Buscar por: nombre de la fruta, nombre del exportador."
    list_filter = ('exportador', 'fecha')
    resource_class = ListaPreciosImportacionResource

@admin.register(ListaPreciosVentas)
class ListaPreciosVentasAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('presentacion', 'precio_euro', 'cliente', 'fecha')
    search_fields = ('presentacion__fruta__nombre', 'cliente__nombre')
    search_help_text = "Buscar por: nombre de la fruta, nombre del cliente."
    list_filter = ('cliente', 'fecha')
    resource_class = ListaPreciosVentasResource
