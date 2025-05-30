from import_export import resources
from .models import Cliente, Venta, DetalleVenta, TranferenciasCliente, BalanceCliente, Cotizacion, DetalleCotizacion

class ClienteResource(resources.ModelResource):
    class Meta:
        model = Cliente
        fields = ('id', 'nombre', 'domicilio', 'ciudad', 'cif', 'email', 'email2', 'telefono', 'dias_pago')

class VentaResource(resources.ModelResource):
    class Meta:
        model = Venta
        fields = ('id', 'cliente', 'fecha_entrega', 'fecha_vencimiento', 'semana', 'numero_factura', 'iva',
                  'subtotal_factura', 'valor_total_factura_euro', 'valor_total_abono_euro', 'numero_nc',
                  'pagado', 'observaciones')

class DetalleVentaResource(resources.ModelResource):
    class Meta:
        model = DetalleVenta
        fields = ('id', 'venta', 'presentacion', 'kilos', 'cajas_envidadas', 'valor_x_caja_euro', 
                  'valor_x_producto', 'no_cajas_abono', 'valor_abono_euro')

class TranferenciasClienteResource(resources.ModelResource):
    class Meta:
        model = TranferenciasCliente
        fields = ('id', 'cliente', 'referencia', 'fecha_transferencia', 'valor_transferencia', 'concepto')

class BalanceClienteResource(resources.ModelResource):
    class Meta:
        model = BalanceCliente
        fields = ('id', 'cliente', 'saldo_disponible', 'ultima_actualizacion')

class CotizacionResource(resources.ModelResource):
    class Meta:
        model = Cotizacion
        fields = (
            'id', 'numero', 'cliente', 'prospect_nombre', 'prospect_email', 'prospect_direccion',
            'prospect_telefono', 'fecha_emision', 'fecha_validez', 'estado', 'terminos', 'notas'
        )

class DetalleCotizacionResource(resources.ModelResource):
    class Meta:
        model = DetalleCotizacion
        fields = ('id', 'cotizacion', 'presentacion', 'precio_unitario')
