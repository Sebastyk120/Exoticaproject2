from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from import_export.admin import ImportExportModelAdmin
from .models import (
    ProveedorNacional, Empaque, CompraNacional, VentaNacional,
    ReporteCalidadExportador, ReporteCalidadProveedor,
    TransferenciasProveedor, FacturacionExportadores, BalanceProveedor
)
from .resources import (
    ProveedorNacionalResource, EmpaqueResource, CompraNacionalResource,
    VentaNacionalResource, ReporteCalidadExportadorResource, ReporteCalidadProveedorResource,
    TransferenciasProveedorResource, FacturacionExportadoresResource, BalanceProveedorResource
)
from comercial.templatetags.custom_filters import format_currency
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ExportForm, ImportForm, SelectableFieldsExportForm
from unfold.admin import TabularInline

@admin.register(ProveedorNacional)
class ProveedorNacionalAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('nombre', 'telefono', 'email', 'asohofrucol', 'rte_fte', 'rte_ica')
    search_fields = ('nombre', 'email')
    search_help_text = "Buscar por: nombre, email."
    list_filter = ('nombre',)
    resource_class = ProveedorNacionalResource

@admin.register(Empaque)
class EmpaqueAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('nombre', 'peso')
    search_fields = ('nombre',)
    search_help_text = "Buscar por: nombre."
    list_filter = ('nombre',)
    resource_class = EmpaqueResource

class VentaNacionalInline(TabularInline):
    model = VentaNacional
    extra = 0
    fields = ('exportador', 'fecha_llegada', 'cantidad_empaque_recibida', 'peso_bruto_recibido')
    show_change_link = True
    classes = ("collapse",)
    verbose_name = "Venta nacional"
    verbose_name_plural = "Ventas nacionales"

@admin.register(CompraNacional)
class CompraNacionalAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('id', 'numero_guia', 'proveedor', 'fruta', 'peso_compra', 'fecha_compra', 'precio_compra_exp', 'precio_compra_nal', 'cantidad_empaque')
    search_fields = ('proveedor__nombre', 'numero_guia', 'fruta__nombre')
    search_help_text = "Buscar por: nombre del proveedor, número de guía y nombre de la fruta."
    list_filter = ('origen_compra', 'fecha_compra', 'proveedor')
    resource_class = CompraNacionalResource
    inlines = [VentaNacionalInline]

@admin.register(VentaNacional)
class VentaNacionalAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('pk', 'compra_nacional', 'exportador', 'fecha_llegada', 'fecha_vencimiento', 'cantidad_empaque_recibida', 'peso_bruto_recibido', 'peso_neto_recibido', 'diferencia_peso', 'diferencia_empaque', 'estado_venta')
    search_fields = ('compra_nacional__numero_guia', 'exportador__nombre')
    search_help_text = "Buscar por: número de guía de la compra y nombre del exportador."
    list_filter = ('exportador',)
    resource_class = VentaNacionalResource

@admin.register(ReporteCalidadExportador)
class ReporteCalidadExportadorAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('pk', 'venta_nacional', 'remision_exp', 'fecha_reporte', 'kg_totales', 'kg_exportacion', 'porcentaje_exportacion', 'kg_nacional', 'porcentaje_nacional',  'kg_merma', 'porcentaje_merma', 'precio_venta_kg_exp', 'precio_venta_kg_nal', 'precio_total', 'factura', 'fecha_factura', 'vencimiento_factura', 'pagado', 'estado_reporte_exp')
    search_fields = ('venta_nacional__compra_nacional__numero_guia',)
    search_help_text = "Buscar por: número de guía de la compra nacional relacionada con la venta."
    list_filter = ('fecha_reporte',)
    resource_class = ReporteCalidadExportadorResource

@admin.register(ReporteCalidadProveedor)
class ReporteCalidadProveedorAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('pk', 'rep_cal_exp', 'p_fecha_reporte', 'p_kg_totales', 'p_kg_exportacion', 'p_porcentaje_exportacion', 'p_kg_nacional', 'p_porcentaje_nacional', 'p_kg_merma', 'p_porcentaje_merma', 'p_total_facturar', 'asohofrucol', 'rte_fte', 'rte_ica', 'p_total_pagar', 'p_utilidad', 'p_porcentaje_utilidad', 'reporte_pago', 'estado_reporte_prov', 'completado')
    search_fields = ('rep_cal_exp__venta_nacional__compra_nacional__numero_guia',)
    search_help_text = "Buscar por: número de guía de la compra nacional (a través de rep_cal_exp)."
    list_filter = ('p_fecha_reporte',)
    resource_class = ReporteCalidadProveedorResource

@admin.register(TransferenciasProveedor)
class TransferenciasProveedorAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('proveedor', 'referencia', 'fecha_transferencia', 'valor_transferencia_moneda', 'origen_transferencia')
    search_fields = ('proveedor__nombre',)
    search_help_text = "Buscar por: nombre del proveedor."
    list_filter = ('origen_transferencia', 'fecha_transferencia')
    resource_class = TransferenciasProveedorResource

    def valor_transferencia_moneda(self, obj):
        return format_currency(obj.valor_transferencia)

    valor_transferencia_moneda.short_description = 'Valor Transferencia'

@admin.register(FacturacionExportadores)
class FacturacionExportadoresAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('id', 'no_factura', 'fecha_factura', 'fruta', 'exportador', 'peso_kg', 'precio_kg_moneda', 'precio_total_moneda')
    search_fields = ('no_factura', 'fruta__nombre', 'exportador__nombre')
    search_help_text = "Buscar por: número de factura, nombre de la fruta y nombre del exportador."
    list_filter = ('fecha_factura',)
    resource_class = FacturacionExportadoresResource

    def precio_total_moneda(self, obj):
        return format_currency(obj.precio_total)

    precio_total_moneda.short_description = 'Total Factura'

    def precio_kg_moneda(self, obj):
        return format_currency(obj.precio_kg)

    precio_kg_moneda.short_description = 'Precio Kg'

@admin.register(BalanceProveedor)
class BalanceProveedorAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('proveedor', 'saldo_disponible_moneda', 'ultima_actualizacion')
    search_fields = ('proveedor__nombre',)
    search_help_text = "Buscar por: nombre del proveedor."
    list_filter = ('ultima_actualizacion',)
    resource_class = BalanceProveedorResource
    readonly_fields = ('proveedor', 'saldo_disponible', 'ultima_actualizacion')
    
    def saldo_disponible_moneda(self, obj):
        return format_currency(obj.saldo_disponible)
    
    saldo_disponible_moneda.short_description = 'Saldo Disponible'
    
    def has_add_permission(self, request):
        # Disable manual creation as balances are created by signals
        return False
