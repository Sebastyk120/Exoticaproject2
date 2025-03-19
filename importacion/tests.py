from django.db import models

class ReporteCalidadProveedor(models.Model):
    p_fecha_reporte = models.DateField(verbose_name="Fecha Reporte Prov", auto_now_add=True)
    p_kg_totales = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Kg Totales", validators=[MinValueValidator(0.0)], editable=False)
    p_kg_exportacion = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Kg Exp", validators=[MinValueValidator(0.0)], blank=True, null=True)
    p_porcentaje_exportacion = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="% Exp", validators=[MinValueValidator(0.0), MaxValueValidator(100.00)], editable=False)
    p_precio_kg_exp = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="$ Kg Exp", validators=[MinValueValidator(0.0)], editable=False)
    p_kg_nacional = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Kg Nal", validators=[MinValueValidator(0.0)], blank=True, null=True)
    p_porcentaje_nacional = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="% Nal", validators=[MinValueValidator(0.0), MaxValueValidator(100.00)], editable=False)
    p_precio_kg_nal = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="$ Kg Nal", validators=[MinValueValidator(0.0)], editable=False)
    p_kg_merma = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Kg Merma", validators=[MinValueValidator(0.0)], editable=False)
    p_porcentaje_merma = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="% Merma", validators=[MinValueValidator(0.0), MaxValueValidator(100.00)], editable=False)
    p_total_facturar = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Facturar", validators=[MinValueValidator(0.0)], editable=False)
    asohofrucol = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Asohofrucol 1%", validators=[MinValueValidator(0.0)], editable=False, default=0)
    rte_fte = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Rte Fte 1.5%", validators=[MinValueValidator(0.0)], editable=False, default=0)
    rte_ica = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Rte Ica 4.14/1000", validators=[MinValueValidator(0.0)], editable=False, default=0)
    p_total_pagar = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total A Pagar", validators=[MinValueValidator(0.0)], editable=False, default=0)
    p_utilidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Utilidad", validators=[MinValueValidator(0.0)], editable=False, default=0)
    p_porcentaje_utilidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="% Utilidad", validators=[MinValueValidator(0.0), MaxValueValidator(100.00)], editable=False)
    reporte_enviado = models.BooleanField(default=False, verbose_name="Reporte Enviado")
    factura_prov = models.CharField(max_length=20, verbose_name="No Factura Proveedor", blank=True, null=True)
    reporte_pago = models.BooleanField(default=False, verbose_name="Reporte Pago", editable=False)
    estado_reporte_prov = models.CharField(max_length=50, verbose_name="Estado Reporte Prov", default='En Proceso', editable=False)
    completado = models.BooleanField(default=False, verbose_name="Completado")

    class Meta:
        ordering = ['-pk']

    @property
    def id(self):
        return self.pk

    def clean(self):
        # RreporteCalidadExportador no ha sido asignado.
        if not self.rep_cal_exp_id:
            return
            
        # Validación de completado
        pago_exportador = self.rep_cal_exp.pagado
        
        if self.completado:
            if self.factura_prov is None:
                raise ValidationError({
                    'factura_prov': 'Este campo es obligatorio si el reporte está completado.'
                })
            elif not self.reporte_enviado:
                raise ValidationError({
                    'reporte_enviado': 'Este campo es obligatorio si el reporte está completado.'
                })
            elif not pago_exportador:
                raise ValidationError(
                    'El reporte no puede ser completado si el exportador(Reporte Calidad Exportador) no ha registrado el pago.'
                )
            elif not self.reporte_pago:
                raise ValidationError(
                    'El reporte no puede ser completado si no se ha registrado el pago por el sistema.'
                )

        # Validación de campos relacionados
        if (self.p_kg_exportacion is None and self.p_kg_nacional is not None) or \
                (self.p_kg_exportacion is not None and self.p_kg_nacional is None):
            raise ValidationError("Ambos campos (Kg exportación y Kg nacional) deben estar completos o vacíos.")

        # Validaciones de pesos cuando tenemos la información necesaria
        if self.rep_cal_exp.venta_nacional.peso_neto_recibido and self.p_kg_exportacion and self.p_kg_nacional:
            total = self.rep_cal_exp.venta_nacional.peso_neto_recibido
            
            # Validación kg_exportacion
            if self.p_kg_exportacion > total:
                raise ValidationError({
                    'p_kg_exportacion': f"El valor no puede ser mayor que el peso neto recibido. ({total})"
                })
                
            # Validación kg_nacional
            if self.p_kg_nacional > total:
                raise ValidationError({
                    'p_kg_nacional': f"El valor no puede ser mayor que el peso neto recibido. ({total})"
                })
                
            # Validación suma total
            computed_p_kg_merma = total - self.p_kg_exportacion - self.p_kg_nacional
            if computed_p_kg_merma < Decimal('0.00'):
                raise ValidationError(f"La suma de Kg exportación y Kg nacional no puede superar el peso neto recibido. ({total})")
                
        super().clean()

    def save(self, *args, **kwargs):
        if self.p_kg_exportacion is None:
            self.p_kg_exportacion = self.rep_cal_exp.kg_exportacion
        if self.p_kg_nacional is None:
            self.p_kg_nacional = self.rep_cal_exp.kg_nacional
        if self.p_kg_merma is None:
            self.p_kg_merma = self.rep_cal_exp.kg_merma
        self.p_kg_totales = self.rep_cal_exp.venta_nacional.peso_neto_recibido
        self.p_precio_kg_exp = self.rep_cal_exp.venta_nacional.compra_nacional.precio_compra_exp
        self.p_porcentaje_exportacion = (self.p_kg_exportacion / self.p_kg_totales * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.p_precio_kg_nal = self.rep_cal_exp.venta_nacional.compra_nacional.precio_compra_nal
        self.p_porcentaje_nacional = (self.p_kg_nacional / self.p_kg_totales * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.p_kg_merma = (self.p_kg_totales - self.p_kg_exportacion - self.p_kg_nacional).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.p_porcentaje_merma = (self.p_kg_merma / self.p_kg_totales * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.p_total_facturar = (self.p_kg_exportacion * self.p_precio_kg_exp) + (self.p_kg_nacional * self.p_precio_kg_nal)
        if self.reporte_enviado:
            self.estado_reporte_prov = "Reporte Enviado"
        if self.reporte_pago:
            self.estado_reporte_prov = "Pagado"
        if self.factura_prov:
            self.estado_reporte_prov = "Facturado Por Proveedor"
        if self.completado:
            self.estado_reporte_prov = "Completado"

        proveedor = self.rep_cal_exp.venta_nacional.compra_nacional.proveedor
        if proveedor.asohofrucol:
            self.asohofrucol = self.p_total_facturar * Decimal("1.00") / Decimal("100.00")
        else:
            self.asohofrucol = Decimal("0.00")
        if proveedor.rte_fte:
            self.rte_fte = self.p_total_facturar * Decimal("1.50") / Decimal("100.00")
        else:
            self.rte_fte = Decimal("0.00")
        if proveedor.rte_ica:
            self.rte_ica = self.p_total_facturar * Decimal("4.14") / Decimal("1000.00")
        else:
            self.rte_ica = Decimal("0.00")
            
        self.p_total_pagar = self.p_total_facturar - self.asohofrucol - self.rte_fte - self.rte_ica
        self.p_utilidad = self.rep_cal_exp.precio_total - self.p_total_facturar
        self.p_porcentaje_utilidad = (self.p_utilidad / self.rep_cal_exp.precio_total) * Decimal("100.00")
        
        super().save(*args, **kwargs)


class TransferenciasProveedor(models.Model):
    proveedor = models.ForeignKey(ProveedorNacional, on_delete=models.PROTECT, verbose_name="Proveedor")
    referencia = models.CharField(max_length=20, verbose_name="Referencia", unique=True, blank=True, null=True)
    fecha_transferencia = models.DateField(verbose_name="Fecha Transferencia")
    valor_transferencia = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Transferencia", validators=[MinValueValidator(0.0)])
    origen_transferencia = models.CharField(max_length=20, choices=origen_transferencia, verbose_name="Origen Transferencia")
    observaciones = models.TextField(verbose_name="Observaciones", blank=True, null=True)

    class Meta:
        ordering = ['-id']


class BalanceProveedor(models.Model):
    proveedor = models.OneToOneField(ProveedorNacional, on_delete=models.CASCADE, verbose_name="Proveedor")
    saldo_disponible = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Saldo Disponible")
    ultima_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    def __str__(self):
        return f"{self.proveedor.nombre} - Saldo: {self.saldo_disponible}"
    
    class Meta:
        verbose_name = "Balance de Proveedor"
        verbose_name_plural = "Balances de Proveedores"


# Variable global para evitar recursión
_processing_payment = False

def reevaluar_pagos_proveedor(proveedor):
    """Resetea y reevalúa todos los pagos de un proveedor"""
    global _processing_payment
    
    # Evitar recursión
    if _processing_payment:
        return
    
    _processing_payment = True
    try:
        from django.db import connection
        total_transferencias = TransferenciasProveedor.objects.filter(
            proveedor=proveedor
        ).aggregate(total=models.Sum('valor_transferencia'))['total'] or 0
        
        reportes = ReporteCalidadProveedor.objects.filter(
            rep_cal_exp__venta_nacional__compra_nacional__proveedor=proveedor
        ).order_by('rep_cal_exp__venta_nacional__fecha_llegada')
        
        ReporteCalidadProveedor.objects.filter(
            rep_cal_exp__venta_nacional__compra_nacional__proveedor=proveedor
        ).update(reporte_pago=False)
        
        saldo_disponible = total_transferencias
        reportes_pagados_ids = []
        
        for reporte in reportes:
            monto_pagar = reporte.p_total_pagar
            
            if saldo_disponible >= monto_pagar:
                saldo_disponible -= monto_pagar
                reportes_pagados_ids.append(reporte.pk)

        if reportes_pagados_ids:
            ReporteCalidadProveedor.objects.filter(pk__in=reportes_pagados_ids).update(reporte_pago=True)

        balance, created = BalanceProveedor.objects.get_or_create(proveedor=proveedor)
        balance.saldo_disponible = saldo_disponible
        balance.save()
        for reporte in reportes:
            reporte.refresh_from_db()
            if reporte.completado:
                nuevo_estado = "Completado"
            elif reporte.reporte_pago:
                nuevo_estado = "Pagado"
            elif reporte.factura_prov:
                nuevo_estado = "Facturado Por Proveedor"
            elif reporte.reporte_enviado:
                nuevo_estado = "Reporte Enviado"
            else:
                nuevo_estado = "En Proceso"
            
            if reporte.estado_reporte_prov != nuevo_estado:
                reporte.estado_reporte_prov = nuevo_estado
                reporte.save(update_fields=['estado_reporte_prov'])
        
    finally:
        _processing_payment = False


@receiver(post_save, sender=TransferenciasProveedor)
def actualizar_balance_tras_transferencia(sender, instance, **kwargs):
    reevaluar_pagos_proveedor(instance.proveedor)


@receiver(post_delete, sender=TransferenciasProveedor)
def actualizar_balance_tras_eliminar_transferencia(sender, instance, **kwargs):
    reevaluar_pagos_proveedor(instance.proveedor)


@receiver(post_save, sender=ReporteCalidadProveedor)
def verificar_pago_tras_crear_o_editar_reporte(sender, instance, created, **kwargs):
    global _processing_payment
    if (_processing_payment):
        return
        
    proveedor = instance.rep_cal_exp.venta_nacional.compra_nacional.proveedor
    reevaluar_pagos_proveedor(proveedor)


@receiver(post_delete, sender=ReporteCalidadProveedor)
def actualizar_balance_tras_eliminar_reporte(sender, instance, **kwargs):
    proveedor = instance.rep_cal_exp.venta_nacional.compra_nacional.proveedor
    reevaluar_pagos_proveedor(proveedor)