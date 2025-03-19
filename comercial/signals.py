from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.db.models import Sum
from decimal import Decimal

from .models import (
    DetalleVenta, Venta, TranferenciasCliente, BalanceCliente, Cliente
)
from importacion.models import Bodega

@receiver(pre_save, sender=DetalleVenta)
def validar_stock_disponible(sender, instance, **kwargs):
    """
    Verifica que haya suficiente stock en bodega antes de permitir la venta.
    """
    # Si es una actualización, obtenemos el objeto original para calcular la diferencia
    try:
        detalle_anterior = DetalleVenta.objects.get(pk=instance.pk)
        cajas_anteriores = detalle_anterior.cajas_envidadas
    except DetalleVenta.DoesNotExist:
        cajas_anteriores = 0
    
    # Calcular cuántas cajas nuevas se van a usar
    cajas_nuevas = instance.cajas_envidadas - cajas_anteriores
    
    # Si no hay cambio o se están devolviendo cajas, no hay problema
    if cajas_nuevas <= 0:
        return
    
    # Verificar stock en bodega
    try:
        bodega = Bodega.objects.get(presentacion=instance.presentacion)
        if bodega.stock_actual < cajas_nuevas:
            raise ValidationError(f"Stock insuficiente. Solo hay {bodega.stock_actual} cajas disponibles de {instance.presentacion}.")
    except Bodega.DoesNotExist:
        raise ValidationError(f"No existe registro de stock para {instance.presentacion}.")

@receiver(post_save, sender=DetalleVenta)
def actualizar_stock_venta(sender, instance, created, **kwargs):
    """
    Actualiza el stock en Bodega cuando se crea o actualiza un DetalleVenta.
    """
    presentacion = instance.presentacion
    
    try:
        bodega = Bodega.objects.get(presentacion=presentacion)
        
        if created:
            # Si es una creación, simplemente restamos las cajas enviadas
            bodega.stock_actual -= instance.cajas_envidadas
        else:
            # Si es una actualización, primero buscamos el valor anterior
            try:
                detalle_anterior = instance._original_cajas if hasattr(instance, '_original_cajas') else instance.cajas_envidadas
                # Ajustamos la diferencia
                bodega.stock_actual -= (instance.cajas_envidadas - detalle_anterior)
            except:
                # Si no podemos determinar el valor anterior, simplemente restamos el actual
                bodega.stock_actual -= instance.cajas_envidadas
                
        bodega.save()
    except Bodega.DoesNotExist:
        # No hay registro de bodega para esta presentación
        pass

@receiver(post_delete, sender=DetalleVenta)
def restaurar_stock_venta(sender, instance, **kwargs):
    """
    Restaura el stock en Bodega cuando se elimina un DetalleVenta.
    """
    presentacion = instance.presentacion
    
    try:
        bodega = Bodega.objects.get(presentacion=presentacion)
        # Devolvemos las cajas al inventario
        bodega.stock_actual += instance.cajas_envidadas
        bodega.save()
    except Bodega.DoesNotExist:
        # No hay registro de bodega para esta presentación
        pass

# Variable global para evitar recursión
_processing_cliente_payment = False

# ---------- LÓGICA PARA CLIENTES ----------

def reevaluar_pagos_cliente(cliente):
    """Resetea y reevalúa todos los pagos de un cliente"""
    global _processing_cliente_payment
    
    # Evitar recursión
    if _processing_cliente_payment:
        return
    
    _processing_cliente_payment = True
    try:
        total_transferencias = TranferenciasCliente.objects.filter(
            cliente=cliente
        ).aggregate(total=Sum('valor_transferencia'))['total'] or Decimal('0.0')
        
        ventas = Venta.objects.filter(
            cliente=cliente
        ).order_by('fecha_entrega')
        
        # Marcar todas las ventas como no pagadas inicialmente
        Venta.objects.filter(cliente=cliente).update(pagado=False)
        
        # Agrupar ventas por fecha de entrega
        ventas_por_fecha = {}
        for venta in ventas:
            if venta.fecha_entrega not in ventas_por_fecha:
                ventas_por_fecha[venta.fecha_entrega] = []
            ventas_por_fecha[venta.fecha_entrega].append(venta)
        
        saldo_disponible = total_transferencias
        ventas_pagadas_ids = []
        
        # Ordenar las fechas cronológicamente
        fechas_ordenadas = sorted(ventas_por_fecha.keys())
        
        # Procesar las ventas día por día
        continuar_procesando = True
        for fecha in fechas_ordenadas:
            if not continuar_procesando:
                break
                
            ventas_del_dia = ventas_por_fecha[fecha]
            for venta in ventas_del_dia:
                # Usar el valor total de la factura menos el valor de la nota de crédito
                monto_pagar = venta.valor_total_factura_euro
                if venta.valor_total_nc_euro:
                    monto_pagar -= venta.valor_total_nc_euro
                
                if saldo_disponible >= monto_pagar:
                    saldo_disponible -= monto_pagar
                    ventas_pagadas_ids.append(venta.pk)
                else:
                    # Si no hay suficiente saldo para esta venta, detenemos el procesamiento
                    continuar_procesando = False
                    break

        # Marcar como pagadas las ventas que se pudieron cubrir
        if ventas_pagadas_ids:
            Venta.objects.filter(pk__in=ventas_pagadas_ids).update(pagado=True)

        # Actualizar el balance del cliente
        balance, created = BalanceCliente.objects.get_or_create(cliente=cliente)
        balance.saldo_disponible = saldo_disponible
        balance.save()
    
    finally:
        _processing_cliente_payment = False

# ---------- SEÑALES PARA CLIENTES ----------

@receiver(post_save, sender=TranferenciasCliente)
def actualizar_balance_tras_transferencia_cliente(sender, instance, **kwargs):
    reevaluar_pagos_cliente(instance.cliente)

@receiver(post_delete, sender=TranferenciasCliente)
def actualizar_balance_tras_eliminar_transferencia_cliente(sender, instance, **kwargs):
    reevaluar_pagos_cliente(instance.cliente)

@receiver(post_save, sender=Venta)
def verificar_pago_tras_crear_o_editar_venta(sender, instance, created, **kwargs):
    global _processing_cliente_payment
    if (_processing_cliente_payment):
        return
    
    reevaluar_pagos_cliente(instance.cliente)

@receiver(post_delete, sender=Venta)
def actualizar_balance_tras_eliminar_venta(sender, instance, **kwargs):
    reevaluar_pagos_cliente(instance.cliente)
