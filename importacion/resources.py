from import_export import resources
from .models import (
    AgenciaAduana, AgenciaCarga, Exportador, Pedido, DetallePedido, TranferenciasExportador,
    BalanceExportador, GastosAduana, TranferenciasAduana, BalanceGastosAduana, GastosCarga,
    TranferenciasCarga, BalanceGastosCarga, Bodega
)

class AgenciaAduanaResource(resources.ModelResource):
    class Meta:
        model = AgenciaAduana
        fields = ('id', 'nombre')

class AgenciaCargaResource(resources.ModelResource):
    class Meta:
        model = AgenciaCarga
        fields = ('id', 'nombre')

class ExportadorResource(resources.ModelResource):
    class Meta:
        model = Exportador
        fields = ('id', 'nombre', 'email', 'email2', 'telefono', 'datos_bancarios', 'dias_credito')

class PedidoResource(resources.ModelResource):
    class Meta:
        model = Pedido
        fields = ('id', 'exportador', 'fecha_entrega', 'semana', 'awb', 'total_cajas_solicitadas', 
                  'total_cajas_recibidas', 'numero_factura', 'fecha_vencimiento', 'valor_total_factura_usd', 
                  'valor_total_nc_usd', 'valor_factura_eur', 'numero_nc', 'estado_pedido', 'pagado', 'observaciones')

class DetallePedidoResource(resources.ModelResource):
    class Meta:
        model = DetallePedido
        fields = ('id', 'pedido', 'presentacion', 'kilos', 'cajas_solicitadas', 'cajas_recibidas', 
                  'valor_x_caja_usd', 'valor_x_producto', 'no_cajas_nc', 'valor_nc_usd')

class TranferenciasExportadorResource(resources.ModelResource):
    class Meta:
        model = TranferenciasExportador
        fields = ('id', 'exportador', 'referencia', 'fecha_transferencia', 'valor_transferencia', 
                  'valor_transferencia_eur', 'trm', 'concepto')

class BalanceExportadorResource(resources.ModelResource):
    class Meta:
        model = BalanceExportador
        fields = ('id', 'exportador', 'saldo_disponible', 'ultima_actualizacion')

class GastosAduanaResource(resources.ModelResource):
    class Meta:
        model = GastosAduana
        fields = ('id', 'agencia_aduana', 'pedidos', 'numero_factura', 'valor_gastos_aduana', 
                  'pagado', 'numero_nota_credito', 'valor_nota_credito', 'conceptos')

class TranferenciasAduanaResource(resources.ModelResource):
    class Meta:
        model = TranferenciasAduana
        fields = ('id', 'agencia_aduana', 'referencia', 'fecha_transferencia', 'valor_transferencia', 'concepto')

class BalanceGastosAduanaResource(resources.ModelResource):
    class Meta:
        model = BalanceGastosAduana
        fields = ('id', 'agencia_aduana', 'saldo_disponible', 'ultima_actualizacion')

class GastosCargaResource(resources.ModelResource):
    class Meta:
        model = GastosCarga
        fields = ('id', 'agencia_carga', 'pedidos', 'numero_factura', 'valor_gastos_carga',
                  'valor_gastos_carga_eur', 'pagado', 'valor_nota_credito', 'numero_nota_credito', 'conceptos')

class TranferenciasCargaResource(resources.ModelResource):
    class Meta:
        model = TranferenciasCarga
        fields = ('id', 'agencia_carga', 'referencia', 'fecha_transferencia', 'valor_transferencia',
                  'valor_transferencia_eur', 'trm', 'concepto')

class BalanceGastosCargaResource(resources.ModelResource):
    class Meta:
        model = BalanceGastosCarga
        fields = ('id', 'agencia_carga', 'saldo_disponible', 'ultima_actualizacion')

class BodegaResource(resources.ModelResource):
    class Meta:
        model = Bodega
        fields = ('id', 'presentacion', 'stock_actual', 'ultima_actualizacion')
