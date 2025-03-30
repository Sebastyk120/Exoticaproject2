import datetime
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from importacion.models import Exportador, Bodega
from productos.models import Fruta, Presentacion


# Modulo Ventas.

class Cliente(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    domicilio = models.CharField(max_length=255, verbose_name="Domicilio:")
    ciudad = models.CharField(max_length=100, verbose_name="Ciudad", null=True, blank=True)
    cif = models.CharField(max_length=20, verbose_name="Código  CIF", null=True, blank=True)
    email = models.EmailField(verbose_name="Correo")
    email2 = models.EmailField(verbose_name="Correo 2", blank=True, null=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    dias_pago = models.IntegerField(verbose_name="Días de pago", validators=[MinValueValidator(0)])

    def __str__(self):
        return self.nombre

    class Meta:
        ordering = ['nombre']



class Venta(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    fecha_entrega = models.DateField(verbose_name="Fecha Entrega")
    fecha_vencimiento = models.DateField(verbose_name="Fecha Vencimiento", editable=False)
    semana = models.CharField(verbose_name="Semana", null=True, blank=True, editable=False)
    total_cajas_pedido = models.IntegerField(verbose_name="Total Cajas", null=True, blank=True, editable=False)
    numero_factura = models.CharField(max_length=100, verbose_name="Número Factura", null=True, blank=True, editable=False)
    iva = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="IVA 4%", validators=[MinValueValidator(0)], editable=False, default=0)
    subtotal_factura = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Subtotal Factura", editable=False, default=0)
    valor_total_factura_euro = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Factura Euro", null=True, blank=True, editable=False, default=0)
    valor_total_abono_euro = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Abono/Reclamacion Euro", null=True, blank=True, default=0, editable=False)
    numero_nc = models.CharField(max_length=100, verbose_name="Número NC/Reclamacion", null=True, blank=True)
    monto_pendiente = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto Pendiente", null=True, blank=True, default=0, editable=False)
    pagado = models.BooleanField(verbose_name="Pagado", default=False, editable=False)
    observaciones = models.CharField(verbose_name="Observaciones", max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):

        if self.subtotal_factura:
            self.iva = self.subtotal_factura * 4 / 100
            self.valor_total_factura_euro = self.subtotal_factura + (self.subtotal_factura * 4 / 100)
        if self.fecha_entrega is not None:
            semana_numero = self.fecha_entrega.isocalendar()[1]
            ano = self.fecha_entrega.year
            if semana_numero == 1 and self.fecha_entrega.month == 12:
                ano += 1
            if semana_numero >= 52 and self.fecha_entrega.month == 1:
                ano -= 1

            self.semana = f"{semana_numero}-{ano}"
            self.fecha_vencimiento = self.fecha_entrega + datetime.timedelta(days=self.cliente.dias_pago)
        if not self.numero_factura:
            current_year = datetime.datetime.now().year
            last_venta = Venta.objects.filter(numero_factura__startswith=f'{current_year}/').order_by(
                'id').last()
            if last_venta:
                last_consecutive = int(last_venta.numero_factura.split('/')[-1])
                new_consecutive = last_consecutive + 1
            else:
                new_consecutive = 1101
            self.numero_factura = f'{current_year}/{new_consecutive}'
        super(Venta, self).save(*args, **kwargs)

    def reevaluar_pagos_cliente(self):
        """
        Actualiza el monto_pendiente considerando todas las transferencias y abonos
        """
        # Obtener la suma de todas las transferencias asociadas a esta venta
        from django.db.models import Sum
        from decimal import Decimal

        self.monto_pendiente = self.valor_total_factura_euro - self.valor_total_abono_euro
        self.save(update_fields=['monto_pendiente'])
        
        # Verificar si se ha pagado completamente
        self.pagado = (self.monto_pendiente <= 0)
        self.save(update_fields=['pagado'])

    def __str__(self):
        return f"No - {self.pk} - {self.cliente} - {self.fecha_entrega}"

    class Meta:
        ordering = ['-id']


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, verbose_name="Venta")
    presentacion = models.ForeignKey(Presentacion, on_delete=models.CASCADE, verbose_name="Presentación")
    kilos = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Kilos Netos", editable=False, null=True, blank=True)
    cajas_enviadas = models.IntegerField(validators=[MinValueValidator(0)], verbose_name="Cajas Enviadas", null=True, blank=True, default=0)
    valor_x_caja_euro = models.DecimalField(validators=[MinValueValidator(0)], max_digits=10, decimal_places=2, verbose_name="Valor Caja Euro")
    valor_x_producto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Producto", null=True, blank=True, editable=False)
    no_cajas_abono = models.DecimalField(max_digits=10, decimal_places=1, verbose_name="No Cajas Abono/Reclamación", null=True, blank=True, default=0)
    valor_abono_euro = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Abono/Reclamación Euro", null=True, blank=True, default=0, editable=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.pk:
            self._original_cajas = self.cajas_enviadas
    
    def clean(self):
        # Realizar cálculos básicos
        if self.presentacion and self.cajas_enviadas:
            self.kilos = self.presentacion.kilos * self.cajas_enviadas

        # Check if no_cajas_abono is not None rather than truthy/falsy
        if self.no_cajas_abono is not None and self.valor_x_caja_euro:
            # Calculate the value
            calculated_value = self.no_cajas_abono * self.valor_x_caja_euro * Decimal('1.04')
            # Round to 2 decimal places to ensure it fits within the field constraints
            self.valor_abono_euro = calculated_value.quantize(Decimal('0.01'))
        else:
            self.valor_abono_euro = Decimal('0')
        
        # Validar stock disponible
        if self.presentacion and self.cajas_enviadas:
            # Si es una actualización, obtenemos el objeto original para calcular la diferencia
            cajas_anteriores = 0
            if self.pk and hasattr(self, '_original_cajas'):
                cajas_anteriores = self._original_cajas
            
            # Calcular cuántas cajas nuevas se van a usar
            cajas_nuevas = self.cajas_enviadas - cajas_anteriores
            
            # Si hay un aumento en cajas, verificar stock disponible
            if cajas_nuevas > 0:
                try:
                    bodega = Bodega.objects.get(presentacion=self.presentacion)
                    if bodega.stock_actual < cajas_nuevas:
                        raise ValidationError({
                            'cajas_enviadas': f"Stock insuficiente. Solo hay {bodega.stock_actual} cajas disponibles de {self.presentacion}."
                        })
                except Bodega.DoesNotExist:
                    raise ValidationError({
                        'presentacion': f"No existe registro de stock para {self.presentacion}."
                    })
        
        super().clean()
    
    @staticmethod
    def actualizar_totales_venta(venta_id):
        """
        Actualiza los campos calculados de la venta relacionada usando consultas agregadas
        """
        from django.db.models import Sum
        from django.db.models.functions import Coalesce
        from decimal import Decimal
        from django.db import transaction
        
        with transaction.atomic():
            # Calcular totales usando agregación (más eficiente)
            totales = DetalleVenta.objects.filter(venta_id=venta_id).aggregate(
                total_producto=Coalesce(Sum('valor_x_producto'), Decimal('0')),
                total_abono=Coalesce(Sum('valor_abono_euro'), Decimal('0')),
                total_cajas=Coalesce(Sum('cajas_enviadas'), 0)
            )
            
            # Asegurar que tenemos valores numéricos, no None
            subtotal = totales['total_producto']
            total_abono = totales['total_abono']
            total_cajas = totales['total_cajas']
            
            # Calcular IVA (4% del subtotal)
            iva_amount = subtotal * Decimal('0.04')
            total_factura = subtotal + iva_amount
            
            # Actualizar la venta sin llamar a signals (evitando recursión)
            Venta.objects.filter(pk=venta_id).update(
                subtotal_factura=subtotal,
                valor_total_abono_euro=total_abono,
                iva=iva_amount,
                valor_total_factura_euro=total_factura,
                total_cajas_pedido=total_cajas
            )
            
            # Ahora llamamos a reevaluar_pagos_cliente para actualizar el monto_pendiente
            venta = Venta.objects.get(pk=venta_id)
            venta.reevaluar_pagos_cliente()
    
    def save(self, *args, **kwargs):
        # Calculate valor_x_producto from the editable fields
        if self.cajas_enviadas and self.valor_x_caja_euro:
            self.valor_x_producto = self.cajas_enviadas * self.valor_x_caja_euro
        
        # Calculate kilos from presentacion and cajas_enviadas
        if self.presentacion and self.cajas_enviadas:
            self.kilos = self.presentacion.kilos * self.cajas_enviadas
            
        # Calculate valor_abono_euro from no_cajas_abono and valor_x_caja_euro
        if self.no_cajas_abono is not None and self.valor_x_caja_euro:
            # Calculate the value
            calculated_value = self.no_cajas_abono * self.valor_x_caja_euro * Decimal('1.04')
            # Round to 2 decimal places to ensure it fits within the field constraints
            self.valor_abono_euro = calculated_value.quantize(Decimal('0.01'))
        else:
            self.valor_abono_euro = Decimal('0')
            
        self.full_clean()  # Esto llamará a clean() para validar
            
        super().save(*args, **kwargs)
        # Luego actualizar la venta relacionada
        self.actualizar_totales_venta(self.venta_id)
    
    def delete(self, *args, **kwargs):
        venta_id = self.venta_id
        # Primero eliminar el detalle
        super().delete(*args, **kwargs)
        # Luego actualizar la venta relacionada
        self.actualizar_totales_venta(venta_id)

    class Meta:  # Corregido de 'meta' a 'Meta' (case sensitive)
        verbose_name = "Detalle Venta"
        verbose_name_plural = "Detalles Ventas"
        ordering = ['venta', 'presentacion']


class TranferenciasCliente(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    referencia = models.CharField(max_length=100, verbose_name="Referencia")
    fecha_transferencia = models.DateField(verbose_name="Fecha Transferencia")
    valor_transferencia = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Transferencia Euros", validators=[MinValueValidator(0.0)])
    concepto = models.CharField(max_length=255, verbose_name="Concepto", null=True, blank=True)

    class Meta:
        verbose_name = "Transferencia Cliente"
        verbose_name_plural = "Transferencias Cliente"
        ordering = ['cliente', 'fecha_transferencia']

class BalanceCliente(models.Model):
    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    saldo_disponible = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Saldo Disponible")
    ultima_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Balance Cliente"
        verbose_name_plural = "Balances Clientes"
        ordering = ['cliente', 'ultima_actualizacion']

