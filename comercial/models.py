import datetime
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from importacion.models import Exportador
from productos.models import Fruta, Presentacion


# Modulo Ventas.

class Cliente(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    Domicilio = models.CharField(max_length=255, verbose_name="Domicilio:")
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
    iva = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="IVA 4%", validators=[MinValueValidator(0)])
    subtotal_factura = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Subtotal Factura", editable=False, default=0)
    valor_total_factura_euro = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Factura Euro", null=True, blank=True, editable=False, default=0)
    valor_total_abono_euro = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Abono/Reclamacion Euro", null=True, blank=True, default=0, editable=False)
    numero_nc = models.CharField(max_length=100, verbose_name="Número NC/Reclamacion", null=True, blank=True)
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
            last_venta = Venta.objects.filter(numero_factura__startswith=f'FACTURA {current_year}/').order_by(
                'id').last()
            if last_venta:
                last_consecutive = int(last_venta.numero_factura.split('/')[-1])
                new_consecutive = last_consecutive + 1
            else:
                new_consecutive = 1101
            self.numero_factura = f'FACTURA {current_year}/{new_consecutive}'
        super(Venta, self).save(*args, **kwargs)

    def __str__(self):
        return f"No - {self.pk} - {self.cliente} - {self.fecha_entrega}"

    class Meta:
        ordering = ['-id']


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, verbose_name="Venta")
    presentacion = models.ForeignKey(Presentacion, on_delete=models.CASCADE, verbose_name="Presentación")
    kilos = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Kilos Netos", editable=False, null=True, blank=True)
    cajas_envidadas = models.IntegerField(validators=[MinValueValidator(0)], verbose_name="Cajas Enviadas", null=True, blank=True, default=0)
    valor_x_caja_euro = models.DecimalField(validators=[MinValueValidator(0)], max_digits=10, decimal_places=2, verbose_name="Valor Caja Euro")
    valor_x_producto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Producto", null=True, blank=True, editable=False)
    no_cajas_abono = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="No Cajas Abono/Reclamación", null=True, blank=True, default=0)
    valor_abono_euro = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Abono/Reclamación Euro", null=True, blank=True, default=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.pk:
            self._original_cajas = self.cajas_envidadas
    
    def clean(self):
        if self.presentacion and self.cajas_envidadas:
            self.kilos = self.presentacion.kilos * self.cajas_envidadas

        if self.no_cajas_abono:
            self.valor_abono_euro = self.no_cajas_abono * self.valor_x_caja_euro
        
        super().clean()
    
    @staticmethod
    def actualizar_totales_venta(venta_id):
        """
        Actualiza los campos calculados de la venta relacionada usando consultas agregadas
        """
        from django.db.models import Sum
        
        # Obtener la venta
        venta = Venta.objects.get(pk=venta_id)
        
        # Calcular totales usando agregación (más eficiente)
        totales = DetalleVenta.objects.filter(venta_id=venta_id).aggregate(
            total_producto=Sum('valor_x_producto') or 0,
            total_abono=Sum('valor_abono_euro') or 0,
            total_cajas=Sum('cajas_envidadas') or 0
        )
        
        # Asegurar que tenemos valores numéricos, no None
        subtotal = totales['total_producto'] or 0
        total_abono = totales['total_abono'] or 0
        total_cajas = totales['total_cajas'] or 0
        
        # Calcular IVA (4% del subtotal)
        iva_amount = subtotal * 4 / 100
        
        # Actualizar la venta sin llamar a signals (evitando recursión)
        Venta.objects.filter(pk=venta_id).update(
            subtotal_factura=subtotal,
            valor_total_abono_euro=total_abono,
            iva=iva_amount,  # Actualizar el IVA también
            valor_total_factura_euro=subtotal + iva_amount,
            total_cajas_pedido=total_cajas
        )
    
    def save(self, *args, **kwargs):
        # Calculate valor_x_producto from the editable fields
        if self.cajas_envidadas and self.valor_x_caja_euro:
            self.valor_x_producto = self.cajas_envidadas * self.valor_x_caja_euro
        
        # Calculate kilos from presentacion and cajas_envidadas
        if self.presentacion and self.cajas_envidadas:
            self.kilos = self.presentacion.kilos * self.cajas_envidadas
            
        # Calculate valor_abono_euro from no_cajas_abono and valor_x_caja_euro
        if self.no_cajas_abono and self.valor_x_caja_euro:
            self.valor_abono_euro = self.no_cajas_abono * self.valor_x_caja_euro
            
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

