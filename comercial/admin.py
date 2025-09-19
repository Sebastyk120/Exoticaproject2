from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from import_export.admin import ImportExportModelAdmin
from .models import Cliente, Venta, DetalleVenta, TranferenciasCliente, BalanceCliente, Cotizacion, DetalleCotizacion, EmailLog
from .resources import (
    ClienteResource, VentaResource, DetalleVentaResource, 
    TranferenciasClienteResource, BalanceClienteResource,
    CotizacionResource, DetalleCotizacionResource
)
from comercial.templatetags.custom_filters import format_currency
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.admin import TabularInline

@admin.register(Cliente)
class ClienteAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('nombre', 'domicilio', 'ciudad', 'cif', 'email', 'correos_adicionales', 'telefono', 'dias_pago', 'token_acceso')
    search_fields = ('nombre', 'email')
    search_help_text = "Buscar por: nombre, email."
    list_filter = ('ciudad',)
    resource_class = ClienteResource

class DetalleVentaInline(TabularInline):
    model = DetalleVenta
    extra = 0
    fields = ('presentacion', 'cajas_enviadas', 'valor_x_caja_euro', 'no_cajas_abono')
    show_change_link = True
    classes = ("collapse",)
    verbose_name = "Detalle venta"
    verbose_name_plural = "Detalles ventas"



@admin.register(Venta)
class VentaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('id', 'cliente', 'fecha_entrega', 'fecha_vencimiento', 'semana', 
                   'total_cajas_pedido', 'numero_factura', 'iva', 'subtotal_factura', 
                   'valor_total_factura_euro', 'valor_total_abono_euro', 'numero_nc', 'monto_pendiente',
                   'pagado', 'observaciones', 'origen')
    search_fields = ('cliente__nombre', 'numero_factura')
    search_help_text = "Buscar por: nombre del cliente, número de factura."
    list_filter = ('cliente', 'fecha_entrega', 'pagado')
    resource_class = VentaResource
    inlines = [DetalleVentaInline]

@admin.register(DetalleVenta)
class DetalleVentaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('id', 'venta', 'presentacion', 'kilos', 'cajas_enviadas', 
                   'valor_x_caja_euro', 'valor_x_producto', 'no_cajas_abono', 
                   'valor_abono_euro')
    search_fields = ('venta__numero_factura', 'presentacion__fruta__nombre')
    search_help_text = "Buscar por: número de factura, nombre de la fruta."
    list_filter = ('venta__cliente', 'presentacion__fruta')
    resource_class = DetalleVentaResource

@admin.register(TranferenciasCliente)
class TranferenciasClienteAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('cliente', 'referencia', 'fecha_transferencia', 
                   'valor_transferencia', 'concepto')
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
    list_display = ('cliente', 'saldo_disponible', 'ultima_actualizacion')
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

class DetalleCotizacionInline(TabularInline):
    model = DetalleCotizacion
    extra = 0
    fields = ('presentacion', 'precio_unitario')
    show_change_link = True
    classes = ("collapse",)
    verbose_name = "Detalle cotización"
    verbose_name_plural = "Detalles cotización"

@admin.register(Cotizacion)
class CotizacionAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('numero', 'cliente', 'prospect_nombre', 'fecha_emision', 'fecha_validez', 'estado')
    search_fields = ('numero', 'cliente__nombre', 'prospect_nombre')
    search_help_text = "Buscar por: número, cliente, prospecto."
    list_filter = ('estado', 'fecha_emision', 'cliente')
    resource_class = CotizacionResource
    inlines = [DetalleCotizacionInline]

@admin.register(DetalleCotizacion)
class DetalleCotizacionAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('cotizacion', 'presentacion', 'precio_unitario')
    search_fields = ('cotizacion__numero', 'presentacion__fruta__nombre')
    search_help_text = "Buscar por: número de cotización, nombre de la fruta."
    list_filter = ('cotizacion', 'presentacion')
    resource_class = DetalleCotizacionResource

@admin.register(EmailLog)
class EmailLogAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ('proceso', 'asunto', 'fecha_envio', 'usuario', 'estado_envio', 'cliente', 'venta', 'cotizacion')
    search_fields = ('asunto', 'destinatarios', 'cliente__nombre', 'venta__numero_factura', 'cotizacion__numero')
    search_help_text = "Buscar por: asunto, destinatarios, cliente, número de factura, número de cotización."
    list_filter = ('proceso', 'estado_envio', 'fecha_envio', 'usuario')
    readonly_fields = ('fecha_envio', 'respuesta_api')
    date_hierarchy = 'fecha_envio'
    
    fieldsets = (
        ('Información del Proceso', {
            'fields': ('proceso', 'fecha_envio', 'usuario', 'estado_envio')
        }),
        ('Información del Correo', {
            'fields': ('asunto', 'destinatarios', 'cuerpo_mensaje', 'documentos_adjuntos')
        }),
        ('Referencias', {
            'fields': ('cliente', 'venta', 'cotizacion'),
            'classes': ('collapse',)
        }),
        ('Respuesta del Sistema', {
            'fields': ('respuesta_api', 'mensaje_error'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Los logs de email se crean automáticamente, no manualmente
        return False
