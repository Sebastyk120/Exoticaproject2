from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from import_export.admin import ImportExportModelAdmin
from .models import Cliente, Venta, DetalleVenta, TranferenciasCliente, BalanceCliente
from .resources import (
    ClienteResource, VentaResource, DetalleVentaResource, 
    TranferenciasClienteResource, BalanceClienteResource
)
from comercial.templatetags.custom_filters import format_currency
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.admin import TabularInline

@admin.register(Cliente)
class ClienteAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('nombre', 'ciudad', 'cif', 'email', 'telefono', 'dias_pago')
    search_fields = ('nombre', 'email')
    search_help_text = "Buscar por: nombre, email."
    list_filter = ('ciudad',)
    resource_class = ClienteResource

class DetalleVentaInline(TabularInline):
    model = DetalleVenta
    extra = 0
    fields = ('presentacion', 'cajas_envidadas', 'valor_x_caja_euro', 'valor_x_producto')
    show_change_link = True
    classes = ("collapse",)
    verbose_name = "Detalle venta"
    verbose_name_plural = "Detalles ventas"

@admin.register(Venta)
class VentaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('id', 'cliente', 'fecha_entrega', 'fecha_vencimiento', 'semana', 'numero_factura', 
                    'subtotal_factura', 'valor_total_factura_euro', 'pagado')
    search_fields = ('cliente__nombre', 'numero_factura')
    search_help_text = "Buscar por: nombre del cliente, número de factura."
    list_filter = ('cliente', 'fecha_entrega', 'pagado')
    resource_class = VentaResource
    inlines = [DetalleVentaInline]

@admin.register(DetalleVenta)
class DetalleVentaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('id', 'venta', 'presentacion', 'kilos', 'cajas_envidadas', 'valor_x_caja_euro', 'valor_x_producto')
    search_fields = ('venta__numero_factura', 'presentacion__fruta__nombre')
    search_help_text = "Buscar por: número de factura, nombre de la fruta."
    list_filter = ('venta__cliente', 'presentacion__fruta')
    resource_class = DetalleVentaResource

@admin.register(TranferenciasCliente)
class TranferenciasClienteAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('cliente', 'referencia', 'fecha_transferencia', 'valor_transferencia_moneda', 'concepto')
    search_fields = ('cliente__nombre', 'referencia')
    search_help_text = "Buscar por: nombre del cliente, referencia."
    list_filter = ('cliente', 'fecha_transferencia')
    resource_class = TranferenciasClienteResource

    def valor_transferencia_moneda(self, obj):
        return format_currency(obj.valor_transferencia)

    valor_transferencia_moneda.short_description = 'Valor Transferencia'

@admin.register(BalanceCliente)
class BalanceClienteAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('cliente', 'saldo_disponible_moneda', 'ultima_actualizacion')
    search_fields = ('cliente__nombre',)
    search_help_text = "Buscar por: nombre del cliente."
    list_filter = ('ultima_actualizacion',)
    resource_class = BalanceClienteResource
    readonly_fields = ('cliente', 'saldo_disponible', 'ultima_actualizacion')
    
    def saldo_disponible_moneda(self, obj):
        return format_currency(obj.saldo_disponible)
    
    saldo_disponible_moneda.short_description = 'Saldo Disponible'
    
    def has_add_permission(self, request):
        # Disable manual creation as balances are created by signals
        return False
