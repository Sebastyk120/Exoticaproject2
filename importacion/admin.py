from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from import_export.admin import ImportExportModelAdmin
from .models import (
    AgenciaAduana, AgenciaCarga, Exportador, Pedido, DetallePedido, TranferenciasExportador,
    BalanceExportador, GastosAduana, TranferenciasAduana, BalanceGastosAduana, GastosCarga,
    TranferenciasCarga, BalanceGastosCarga, Bodega
)
from .resources import (
    AgenciaAduanaResource, AgenciaCargaResource, ExportadorResource, PedidoResource, 
    DetallePedidoResource, TranferenciasExportadorResource, BalanceExportadorResource,
    GastosAduanaResource, TranferenciasAduanaResource, BalanceGastosAduanaResource,
    GastosCargaResource, TranferenciasCargaResource, BalanceGastosCargaResource, BodegaResource
)
from comercial.templatetags.custom_filters import format_currency, format_currency_eur
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.admin import TabularInline

@admin.register(AgenciaAduana)
class AgenciaAduanaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('nombre', 'correo', 'correos_adicionales')
    search_fields = ('nombre', 'correo')
    search_help_text = "Buscar por: nombre, correo."
    resource_class = AgenciaAduanaResource
    list_per_page = 20

@admin.register(AgenciaCarga)
class AgenciaCargaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('nombre', 'correo', 'correos_adicionales')
    search_fields = ('nombre', 'correo')
    search_help_text = "Buscar por: nombre, correo."
    resource_class = AgenciaCargaResource
    list_per_page = 20

@admin.register(Exportador)
class ExportadorAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('nombre', 'email', 'telefono', 'dias_credito')
    search_fields = ('nombre', 'email')
    search_help_text = "Buscar por: nombre, email."
    resource_class = ExportadorResource

class DetallePedidoInline(TabularInline):
    model = DetallePedido
    extra = 0
    fields = ('presentacion', 'cajas_solicitadas', 'cajas_recibidas', 'valor_x_caja_usd', 'get_valor_x_producto', 'no_cajas_nc', 'get_valor_nc_usd', 'get_valor_x_producto_eur')
    readonly_fields = ('get_valor_x_producto', 'get_valor_nc_usd', 'get_valor_x_producto_eur')
    show_change_link = True
    classes = ("collapse",)
    verbose_name = "Detalle pedido"
    verbose_name_plural = "Detalles pedidos"
    
    def get_valor_x_producto(self, obj):
        if obj.valor_x_producto is not None:
            return format_currency(obj.valor_x_producto)
        return "-"
    
    def get_valor_nc_usd(self, obj):
        if obj.valor_nc_usd is not None:
            return format_currency(obj.valor_nc_usd)
        return "-"
    
    def get_valor_x_producto_eur(self, obj):
        if obj.valor_x_producto_eur is not None and obj.valor_x_producto_eur > 0:
            return format_currency_eur(obj.valor_x_producto_eur)
        return "-"
    
    get_valor_x_producto.short_description = "Valor Total Producto"
    get_valor_nc_usd.short_description = "Valor Total NC USD"
    get_valor_x_producto_eur.short_description = "Valor Total EUR"
    
@admin.register(Pedido)
class PedidoAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = (
        'id', 'exportador', 'fecha_entrega', 'semana', 'awb',
        'total_cajas_solicitadas', 'total_cajas_recibidas',
        'numero_factura', 'fecha_vencimiento', 'valor_total_factura_usd',
        'valor_total_nc_usd', 'valor_factura_eur', 'numero_nc',
        'estado_pedido', 'pagado', 'monto_pendiente', 'observaciones'
    )
    search_fields = ('exportador__nombre', 'awb', 'numero_factura')
    search_help_text = "Buscar por: nombre del exportador, AWB, número de factura."
    list_filter = ('exportador', 'fecha_entrega', 'pagado')
    resource_class = PedidoResource
    inlines = [DetallePedidoInline]

@admin.register(DetallePedido)
class DetallePedidoAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('id', 'pedido', 'presentacion', 'kilos', 'cajas_solicitadas', 'cajas_recibidas', 
                    'valor_x_caja_usd', 'valor_x_producto', 'valor_x_producto_eur')
    search_fields = ('pedido__awb', 'presentacion__fruta__nombre')
    search_help_text = "Buscar por: AWB del pedido, nombre de la fruta."
    list_filter = ('pedido__exportador', 'presentacion__fruta')
    resource_class = DetallePedidoResource
    exclude = ['valor_x_producto', 'valor_x_producto_eur']  # Exclude non-editable fields

@admin.register(TranferenciasExportador)
class TranferenciasExportadorAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('exportador', 'referencia', 'fecha_transferencia', 'valor_transferencia_moneda', 
                   'valor_transferencia_eur_moneda', 'trm', 'concepto')
    search_fields = ('exportador__nombre', 'referencia')
    search_help_text = "Buscar por: nombre del exportador, referencia."
    list_filter = ('exportador', 'fecha_transferencia')
    resource_class = TranferenciasExportadorResource

    def valor_transferencia_moneda(self, obj):
        return format_currency(obj.valor_transferencia)

    valor_transferencia_moneda.short_description = 'Valor Transferencia USD'
    
    def valor_transferencia_eur_moneda(self, obj):
        return format_currency(obj.valor_transferencia_eur)

    valor_transferencia_eur_moneda.short_description = 'Valor Transferencia EUR'

@admin.register(BalanceExportador)
class BalanceExportadorAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('exportador', 'saldo_disponible_moneda', 'ultima_actualizacion')
    search_fields = ('exportador__nombre',)
    search_help_text = "Buscar por: nombre del exportador."
    list_filter = ('ultima_actualizacion',)
    resource_class = BalanceExportadorResource
    readonly_fields = ('exportador', 'saldo_disponible', 'ultima_actualizacion')
    
    def saldo_disponible_moneda(self, obj):
        return format_currency(obj.saldo_disponible)
    
    saldo_disponible_moneda.short_description = 'Saldo Disponible'
    
    def has_add_permission(self, request):
        return False

@admin.register(GastosAduana)
class GastosAduanaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('id', 'agencia_aduana', 'numero_factura', 'valor_gastos_aduana_moneda', 'pagado',
                   'numero_nota_credito', 'valor_nota_credito', 'monto_pendiente', 'iva_importacion', 'iva_sobre_base')
    search_fields = ('agencia_aduana__nombre', 'numero_factura')
    search_help_text = "Buscar por: nombre de la agencia, número de factura."
    list_filter = ('agencia_aduana', 'pagado')
    resource_class = GastosAduanaResource
    filter_horizontal = ('pedidos',)
    
    def valor_gastos_aduana_moneda(self, obj):
        return format_currency(obj.valor_gastos_aduana)

    valor_gastos_aduana_moneda.short_description = 'Valor Gastos Aduana EUR'

@admin.register(TranferenciasAduana)
class TranferenciasAduanaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('agencia_aduana', 'referencia', 'fecha_transferencia', 'valor_transferencia_moneda', 'concepto')
    search_fields = ('agencia_aduana__nombre', 'referencia')
    search_help_text = "Buscar por: nombre de la agencia, referencia."
    list_filter = ('agencia_aduana', 'fecha_transferencia')
    resource_class = TranferenciasAduanaResource
    
    def valor_transferencia_moneda(self, obj):
        return format_currency(obj.valor_transferencia)

    valor_transferencia_moneda.short_description = 'Valor Transferencia USD'

@admin.register(BalanceGastosAduana)
class BalanceGastosAduanaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('agencia_aduana', 'saldo_disponible_moneda', 'ultima_actualizacion')
    search_fields = ('agencia_aduana__nombre',)
    search_help_text = "Buscar por: nombre de la agencia."
    list_filter = ('ultima_actualizacion',)
    resource_class = BalanceGastosAduanaResource
    readonly_fields = ('agencia_aduana', 'saldo_disponible', 'ultima_actualizacion')
    
    def saldo_disponible_moneda(self, obj):
        return format_currency(obj.saldo_disponible)
    
    saldo_disponible_moneda.short_description = 'Saldo Disponible'
    
    def has_add_permission(self, request):
        return False

@admin.register(GastosCarga)
class GastosCargaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('id', 'agencia_carga', 'numero_factura', 'valor_gastos_carga_moneda', 
                    'valor_gastos_carga_eur_moneda', 'valor_nota_credito', 'numero_nota_credito', 'monto_pendiente','pagado', 'conceptos')
    search_fields = ('agencia_carga__nombre', 'numero_factura')
    search_help_text = "Buscar por: nombre de la agencia, número de factura."
    list_filter = ('agencia_carga', 'pagado')
    resource_class = GastosCargaResource
    filter_horizontal = ('pedidos',)
    
    def valor_gastos_carga_moneda(self, obj):
        return format_currency(obj.valor_gastos_carga)

    valor_gastos_carga_moneda.short_description = 'Valor Gastos Carga'
    
    def valor_gastos_carga_eur_moneda(self, obj):
        return format_currency(obj.valor_gastos_carga_eur)

    valor_gastos_carga_eur_moneda.short_description = 'Valor Gastos Carga EUR'

@admin.register(TranferenciasCarga)
class TranferenciasCargaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('agencia_carga', 'referencia', 'fecha_transferencia', 'valor_transferencia_moneda', 
                    'valor_transferencia_eur_moneda', 'trm', 'concepto')
    search_fields = ('agencia_carga__nombre', 'referencia')
    search_help_text = "Buscar por: nombre de la agencia, referencia."
    list_filter = ('agencia_carga', 'fecha_transferencia')
    resource_class = TranferenciasCargaResource
    
    def valor_transferencia_moneda(self, obj):
        return format_currency(obj.valor_transferencia)

    valor_transferencia_moneda.short_description = 'Valor Transferencia USD'
    
    def valor_transferencia_eur_moneda(self, obj):
        return format_currency(obj.valor_transferencia_eur)

    valor_transferencia_eur_moneda.short_description = 'Valor Transferencia EUR'

@admin.register(BalanceGastosCarga)
class BalanceGastosCargaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('agencia_carga', 'saldo_disponible_moneda', 'ultima_actualizacion')
    search_fields = ('agencia_carga__nombre',)
    search_help_text = "Buscar por: nombre de la agencia."
    list_filter = ('ultima_actualizacion',)
    resource_class = BalanceGastosCargaResource
    readonly_fields = ('agencia_carga', 'saldo_disponible', 'ultima_actualizacion')
    
    def saldo_disponible_moneda(self, obj):
        return format_currency(obj.saldo_disponible)
    
    saldo_disponible_moneda.short_description = 'Saldo Disponible'
    
    def has_add_permission(self, request):
        return False

@admin.register(Bodega)
class BodegaAdmin(ModelAdmin, ImportExportModelAdmin, SimpleHistoryAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_display = ('presentacion', 'stock_actual', 'ultima_actualizacion')
    search_fields = ('presentacion__fruta__nombre',)
    search_help_text = "Buscar por: nombre de la fruta."
    list_filter = ('presentacion__fruta',)
    resource_class = BodegaResource
