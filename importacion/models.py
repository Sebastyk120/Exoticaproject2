from datetime import timedelta
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Sum, DecimalField, IntegerField
from productos.models import Presentacion

def validate_awb(value):
    if len(value) != 12:
        raise ValidationError(
            'El AWB debe tener exactamente 12 caracteres.',
            params={'value': value},
        )
    if ' ' in value:
        raise ValidationError(
            'El AWB no puede contener espacios.',
            params={'value': value},
        )

class AgenciaAduana(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre

class AgenciaCarga(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre

class Exportador(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    email = models.EmailField(verbose_name="Correo")
    email2 = models.EmailField(verbose_name="Correo 2", blank=True, null=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    datos_bancarios = models.CharField(max_length=255, verbose_name="Datos Bancarios", null=True, blank=True)
    dias_credito = models.IntegerField(verbose_name="Días Crédito", default=0, validators=[MinValueValidator(0)])

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Exportador"
        verbose_name_plural = "Exportadores"
        ordering = ['nombre']

# ------------------- PROCESO DE COMPRA --------------------

class Pedido(models.Model):
    exportador = models.ForeignKey(Exportador, on_delete=models.CASCADE, verbose_name="Exportador")
    fecha_entrega = models.DateField(verbose_name="Fecha Entrega")
    semana = models.CharField(verbose_name="Semana", null=True, blank=True, editable=False)
    awb = models.CharField(max_length=12, verbose_name="AWB", null=True, blank=True, default=None,
                           validators=[validate_awb])
    total_cajas_solicitadas = models.IntegerField(verbose_name="Cajas Solicitadas", null=True, blank=True, editable=False)
    total_cajas_recibidas = models.IntegerField(verbose_name="Cajas Recibidas", null=True, blank=True, editable=False)
    numero_factura = models.CharField(max_length=100, verbose_name="Número Factura", null=True, blank=True)
    fecha_vencimiento = models.DateField(verbose_name="Vencimiento Factura", null=True, blank=True, editable=False)
    valor_total_factura_usd = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Factura USD",
                                                  null=True, blank=True, editable=False, default=0)
    valor_total_nc_usd = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total NC USD", null=True, blank=True, default=0, editable=False)
    valor_factura_eur = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Factura EUR", null=True, blank=True, editable=False)
    numero_nc = models.CharField(max_length=100, verbose_name="Número NC", null=True, blank=True)
    estado_pedido = models.CharField(verbose_name="Estado del Pedido", default="En Proceso", editable=False)
    pagado = models.BooleanField(verbose_name="Pagado", default=False, editable=False)
    observaciones = models.CharField(verbose_name="Observaciones", max_length=100, blank=True, null=True)
    monto_pendiente = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto Pendiente USD", 
                                         null=True, blank=True, editable=False, default=0)
    
    def save(self, *args, **kwargs):
        if self.fecha_entrega is not None:
            semana_numero = self.fecha_entrega.isocalendar()[1]
            ano = self.fecha_entrega.year
            if semana_numero == 1 and self.fecha_entrega.month == 12:
                ano += 1

            if semana_numero >= 52 and self.fecha_entrega.month == 1:
                ano -= 1

            self.semana = f"{semana_numero}-{ano}"
            self.fecha_vencimiento = self.fecha_entrega + timedelta(days=self.exportador.dias_credito)
        super(Pedido, self).save(*args, **kwargs)

    def __str__(self):
        return f"No: {self.pk} - {self.fecha_entrega} - {self.awb}"

    class Meta:
        ordering = ['-id']

class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, verbose_name="Pedido")
    presentacion = models.ForeignKey(Presentacion, on_delete=models.CASCADE, verbose_name="Presentación")
    kilos = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Kilos Netos", editable=False, blank=True, null=True)
    cajas_solicitadas = models.IntegerField(validators=[MinValueValidator(0)], verbose_name="Cajas Solicitadas", null=True,
                                         blank=True, default=0)
    cajas_recibidas = models.IntegerField(validators=[MinValueValidator(0)], verbose_name="Cajas Recibidas",
                                            null=True,
                                            blank=True, default=0)
    valor_x_caja_usd = models.DecimalField(validators=[MinValueValidator(0)], max_digits=10, decimal_places=2,
                                           verbose_name="Valor Caja USD")
    valor_x_producto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Producto", null=True,
                                           blank=True, editable=False)
    valor_x_producto_eur = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Producto EUR", blank=True, null=True, editable=False, default=0)
    no_cajas_nc = models.DecimalField(max_digits=10, decimal_places=1, verbose_name="No Cajas NC", null=True,
                                      blank=True, default=0)
    valor_nc_usd = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor NC USD", default=0, editable=False)

    def clean(self):
        # Importamos aquí también para asegurar que está disponible
        from decimal import Decimal, InvalidOperation
        
        # Para kilos
        if self.presentacion and self.cajas_recibidas is not None:
            try:
                kilos_presentacion = Decimal(str(self.presentacion.kilos))
                cajas_decimal = Decimal(str(self.cajas_recibidas))
                self.kilos = kilos_presentacion * cajas_decimal
            except (ValueError, TypeError, InvalidOperation):
                self.kilos = Decimal('0')
        else:
            self.kilos = Decimal('0')

        # Para valor_x_producto
        if self.cajas_recibidas is not None and self.valor_x_caja_usd is not None:
            try:
                cajas_decimal = Decimal(str(self.cajas_recibidas))
                valor_caja_decimal = Decimal(str(self.valor_x_caja_usd))
                self.valor_x_producto = cajas_decimal * valor_caja_decimal
            except (ValueError, TypeError, InvalidOperation):
                self.valor_x_producto = Decimal('0')
        else:
            self.valor_x_producto = Decimal('0')
        
        # Para valor_nc_usd
        if self.no_cajas_nc is not None and self.no_cajas_nc != '' and self.valor_x_caja_usd is not None:
            try:
                no_cajas_decimal = Decimal(str(self.no_cajas_nc)) if self.no_cajas_nc else Decimal('0')
                valor_caja_decimal = Decimal(str(self.valor_x_caja_usd))
                self.valor_nc_usd = (no_cajas_decimal * valor_caja_decimal).quantize(Decimal('0.00'))
            except (ValueError, TypeError, InvalidOperation):
                self.valor_nc_usd = Decimal('0')
        else:
            self.valor_nc_usd = Decimal('0')

        super().clean()
        
    @staticmethod
    def actualizar_totales_pedido(pedido_id):
        """
        
        Actualiza los campos calculados del pedido relacionado usando consultas agregadas
        y luego llama a reevaluar_pagos_exportador para actualizar el monto pendiente.
        """
        # Importación diferida aquí para evitar ciclo
        from importacion.signals import reevaluar_pagos_exportador
        from decimal import Decimal
        from django.db.models.functions import Coalesce
        
        # Separar las consultas por tipo de campo para evitar mezcla de tipos
        # Consulta para campos enteros
        totales_enteros = DetallePedido.objects.filter(pedido_id=pedido_id).aggregate(
            total_cajas_solicitadas=Coalesce(Sum('cajas_solicitadas', output_field=IntegerField()), 0),
            total_cajas_recibidas=Coalesce(Sum('cajas_recibidas', output_field=IntegerField()), 0)
        )
        
        # Consulta para campos decimales
        totales_decimales = DetallePedido.objects.filter(pedido_id=pedido_id).aggregate(
            total_factura=Coalesce(Sum('valor_x_producto', output_field=DecimalField(max_digits=10, decimal_places=2)), Decimal('0')),
            total_nc=Coalesce(Sum('valor_nc_usd', output_field=DecimalField(max_digits=10, decimal_places=2)), Decimal('0'))
        )
        
        # Usar update para evitar disparar señales innecesarias
        with transaction.atomic():
            Pedido.objects.filter(pk=pedido_id).update(
                total_cajas_solicitadas=totales_enteros['total_cajas_solicitadas'],
                total_cajas_recibidas=totales_enteros['total_cajas_recibidas'],
                valor_total_factura_usd=totales_decimales['total_factura'],
                valor_total_nc_usd=totales_decimales['total_nc']
            )
        
        # Obtener el exportador y reevaluar los pagos
        try:
            pedido = Pedido.objects.select_related('exportador').get(pk=pedido_id)
            
            # Calcular valor_x_producto_eur para los detalles cuando pedido.pagado es True
            if pedido.pagado and pedido.valor_total_factura_usd > Decimal('0'):
                # Calcular el total neto de la factura
                valor_neto_factura = pedido.valor_total_factura_usd - pedido.valor_total_nc_usd
                
                # Obtener todos los detalles del pedido
                detalles = DetallePedido.objects.filter(pedido=pedido)
                
                for detalle in detalles:
                    # Calcular el valor neto del detalle
                    valor_neto_detalle = detalle.valor_x_producto - detalle.valor_nc_usd
                    
                    # Evitar división por cero
                    if valor_neto_factura > Decimal('0') and valor_neto_detalle > Decimal('0'):
                        # Calcular la proporción para este detalle 
                        proporcion = valor_neto_detalle / valor_neto_factura
                        
                        # Calcular el valor en EUR como proporción del total facturado
                        if pedido.valor_factura_eur is not None and pedido.valor_factura_eur > Decimal('0'):
                            detalle.valor_x_producto_eur = (proporcion * pedido.valor_factura_eur).quantize(Decimal('0.00'))
                            # Evitar recursión usando update() directo sobre el modelo en lugar de save()
                            DetallePedido.objects.filter(pk=detalle.pk).update(valor_x_producto_eur=detalle.valor_x_producto_eur)
            
            # Llamar a reevaluar_pagos_exportador para actualizar el monto pendiente
            reevaluar_pagos_exportador(pedido.exportador)
        except Pedido.DoesNotExist:
            pass
    
    def save(self, *args, **kwargs):
        # Verificar si debemos saltarnos la actualización de totales
        skip_update = kwargs.pop('skip_update', False)
        
        # Asegurarnos de que todos los cálculos se realizan antes de guardar
        self.full_clean()  # Esto llamará a clean()
        
        # Guardar el objeto
        super().save(*args, **kwargs)
        
        # Actualizar totales del pedido relacionado, solo si no estamos saltándonos la actualización
        if self.pedido_id and not skip_update:
            self.actualizar_totales_pedido(self.pedido_id)
    
    def delete(self, *args, **kwargs):
        pedido_id = self.pedido_id
        # Primero eliminar el detalle
        super().delete(*args, **kwargs)
        # Luego actualizar el pedido relacionado
        if pedido_id:
            self.actualizar_totales_pedido(pedido_id)

    class Meta:
        verbose_name = "Detalle Pedido"
        verbose_name_plural = "Detalles Pedido"
        ordering = ['pedido', 'presentacion']

class TranferenciasExportador(models.Model):
    exportador = models.ForeignKey(Exportador, on_delete=models.CASCADE, verbose_name="Exportador")
    referencia = models.CharField(max_length=100, verbose_name="Referencia")
    fecha_transferencia = models.DateField(verbose_name="Fecha Transferencia")
    valor_transferencia = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Transferencia USD", validators=[MinValueValidator(0.0)])
    valor_transferencia_eur = models.DecimalField(max_digits=10, decimal_places=2,
                                                  verbose_name="Valor Transferencia EUR",
                                                  validators=[MinValueValidator(0.0)])
    trm = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="TRM", editable=False, blank=True, null=True)
    concepto = models.CharField(max_length=255, verbose_name="Concepto", null=True, blank=True)

    def clean(self):
        if self.valor_transferencia and self.valor_transferencia_eur:
            self.trm = self.valor_transferencia / self.valor_transferencia_eur
        super().clean()

    @property
    def saldo_disponible(self):
        try:
            balance = BalanceExportador.objects.get(exportador=self.exportador)
            return balance.saldo_disponible
        except BalanceExportador.DoesNotExist:
            return 0
    
    @property
    def saldo_transferencia(self):
        """Returns the remaining balance for this specific transfer"""
        # Importación diferida aquí para evitar ciclo
        from importacion.signals import calcular_saldo_transferencia
        return calcular_saldo_transferencia(self)

    class Meta:
        verbose_name = "Transferencia Exportador"
        verbose_name_plural = "Transferencias Exportador"
        ordering = ['exportador', 'fecha_transferencia']

class BalanceExportador(models.Model):
    exportador = models.OneToOneField(Exportador, on_delete=models.CASCADE, verbose_name="Exportador")
    saldo_disponible = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Saldo Disponible")
    ultima_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Balance Exportador"
        verbose_name_plural = "Balances Exportador"
        ordering = ['exportador', 'ultima_actualizacion']

# ------------------- PROCESO DE ADUANA  --------------------

class GastosAduana(models.Model):
    agencia_aduana = models.ForeignKey(AgenciaAduana, on_delete=models.CASCADE, verbose_name="Agencia Aduana")
    pedidos = models.ManyToManyField(Pedido, verbose_name="Pedidos")
    numero_factura = models.CharField(max_length=100, verbose_name="Número Factura", unique=True)
    valor_gastos_aduana = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Gastos Aduana Eur", validators=[MinValueValidator(0.0)])
    pagado = models.BooleanField(verbose_name="Pagado", default=False, editable=False)
    numero_nota_credito = models.CharField(max_length=100, verbose_name="# Abono/Reclamación", null=True, blank=True)
    valor_nota_credito = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Abono/Reclamación", null=True, blank=True)
    monto_pendiente = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto Pendiente EUR", null=True, blank=True, editable=False, default=0)
    conceptos = models.CharField(max_length=1000, verbose_name="Conceptos", null=True, blank=True)

    class Meta:
        verbose_name = "Gastos Aduana"
        verbose_name_plural = "Gastos Aduana"

class TranferenciasAduana(models.Model):
    agencia_aduana = models.ForeignKey(AgenciaAduana, on_delete=models.CASCADE, verbose_name="Agencia Aduana")
    referencia = models.CharField(max_length=100, verbose_name="Referencia")
    fecha_transferencia = models.DateField(verbose_name="Fecha Transferencia")
    valor_transferencia = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Transferencia EUR", validators=[MinValueValidator(0.0)])
    concepto = models.CharField(max_length=255, verbose_name="Concepto", null=True, blank=True)

    class Meta:
        verbose_name = "Transferencia Aduana"
        verbose_name_plural = "Transferencias Aduana"
        ordering = ['agencia_aduana', 'fecha_transferencia']

class BalanceGastosAduana(models.Model):
    agencia_aduana = models.OneToOneField(AgenciaAduana, on_delete=models.CASCADE, verbose_name="Agencia Aduana")
    saldo_disponible = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Saldo Disponible")
    ultima_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Balance Gastos Aduana"
        verbose_name_plural = "Balances Gastos Aduana"
        ordering = ['agencia_aduana', 'ultima_actualizacion']

# ------------------- PROCESO DE AGENCIA DE CARGA  --------------------

class GastosCarga(models.Model):
    agencia_carga = models.ForeignKey(AgenciaCarga, on_delete=models.CASCADE, verbose_name="Agencia Carga")
    pedidos = models.ManyToManyField(Pedido, verbose_name="Pedidos")
    numero_factura = models.CharField(max_length=100, verbose_name="Número Factura", editable=False, unique=True)
    valor_gastos_carga = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Gastos Carga USD", validators=[MinValueValidator(0.0)])
    valor_gastos_carga_eur = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Gastos Carga EUR", validators=[MinValueValidator(0.0)], editable=False, null=True, blank=True)
    pagado = models.BooleanField(verbose_name="Pagado", default=False, editable=False)
    valor_nota_credito = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Nota Crédito USD", null=True, blank=True)
    numero_nota_credito = models.CharField(max_length=100, verbose_name="Abono/Reclamación", null=True, blank=True)
    monto_pendiente = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto Pendiente USD", null=True, blank=True, editable=False, default=0)
    conceptos = models.CharField(max_length=500, verbose_name="Conceptos", null=True, blank=True)

    class Meta:
        verbose_name = "Gastos Carga"
        verbose_name_plural = "Gastos Carga"

class TranferenciasCarga(models.Model):
    agencia_carga = models.ForeignKey(AgenciaCarga, on_delete=models.CASCADE, verbose_name="Agencia Carga")
    referencia = models.CharField(max_length=100, verbose_name="Referencia")
    fecha_transferencia = models.DateField(verbose_name="Fecha Transferencia")
    valor_transferencia = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Transferencia USD", validators=[MinValueValidator(0.0)])
    valor_transferencia_eur = models.DecimalField(max_digits=10, decimal_places=2,
                                                  verbose_name="Valor Transferencia EUR",
                                                  validators=[MinValueValidator(0.0)])
    trm = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="TRM", editable=False, blank=True, null=True)
    concepto = models.CharField(max_length=255, verbose_name="Concepto", null=True, blank=True)

    def clean(self):
        if self.valor_transferencia and self.valor_transferencia_eur:
            self.trm = self.valor_transferencia / self.valor_transferencia_eur
        super().clean()

    class Meta:
        verbose_name = "Transferencia Carga"
        verbose_name_plural = "Transferencias Carga"
        ordering = ['agencia_carga', 'fecha_transferencia']

class BalanceGastosCarga(models.Model):
    agencia_carga = models.OneToOneField(AgenciaCarga, on_delete=models.CASCADE, verbose_name="Agencia Carga")
    saldo_disponible = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Saldo Disponible")
    ultima_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Balance Gastos Carga"
        verbose_name_plural = "Balances Gastos Carga"
        ordering = ['agencia_carga', 'ultima_actualizacion']

# ------------------- BODEGA DE ALMACENAMIENTO --------------------

class Bodega(models.Model):
    presentacion = models.ForeignKey(Presentacion, on_delete=models.CASCADE, verbose_name="Presentación")
    stock_actual = models.IntegerField(verbose_name="Stock Actual (Cajas)", default=0)
    ultima_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")
    
    def __str__(self):
        return f"{self.presentacion} - Stock: {self.stock_actual} cajas"
    
    class Meta:
        verbose_name = "Stock Bodega"
        verbose_name_plural = "Stock Bodega"
        ordering = ['presentacion']
        unique_together = ['presentacion']
