from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.db.models import Sum, F, Value
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.db import transaction

from .models import (
    DetalleVenta, Venta, TranferenciasCliente, BalanceCliente, Cliente
)
from importacion.models import Bodega

@receiver(pre_save, sender=DetalleVenta)
def validar_stock_disponible(sender, instance, **kwargs):
    """
    Verifica que haya suficiente stock en bodega antes de permitir la venta.
    Este signal está aquí para compatibilidad, pero la validación real
    ocurre en el método clean() del modelo DetalleVenta.
    """
    # La validación ahora se hace en el método clean() del modelo
    # Este signal se mantiene por compatibilidad con código existente
    pass

@receiver(post_save, sender=DetalleVenta)
def actualizar_stock_venta(sender, instance, created, **kwargs):
    """
    Actualiza el stock en Bodega cuando se crea o actualiza un DetalleVenta.
    Optimizado para evitar actualizaciones innecesarias.
    """
    presentacion = instance.presentacion
    
    try:
        with transaction.atomic():
            bodega = Bodega.objects.select_for_update().get(presentacion=presentacion)
            
            if created:
                # Si es una creación, simplemente restamos las cajas enviadas
                cajas_a_descontar = instance.cajas_enviadas or 0
                bodega.stock_actual -= cajas_a_descontar
            else:
                # Si es una actualización, calcular la diferencia con el valor original
                cajas_anteriores = getattr(instance, '_original_cajas', 0)
                cajas_actuales = instance.cajas_enviadas or 0
                
                # Solo ajustamos la diferencia neta
                diferencia = cajas_actuales - cajas_anteriores
                bodega.stock_actual -= diferencia
                    
            # Garantizar stock no negativo y guardar
            if bodega.stock_actual < 0:
                bodega.stock_actual = 0  # Evitar stock negativo
                
            bodega.save(update_fields=['stock_actual', 'ultima_actualizacion'])
            
            # Registrar la operación para depuración
            import logging
            logger = logging.getLogger('comercial')
            if created:
                logger.info(f"Stock actualizado por venta (nuevo): {presentacion} - {instance.cajas_enviadas} cajas")
            else:
                logger.info(f"Stock actualizado por venta (edición): {presentacion} - Anterior: {cajas_anteriores}, Nuevo: {cajas_actuales}, Diferencia: {diferencia}")
            
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
        bodega.stock_actual += instance.cajas_enviadas
        bodega.save()
    except Bodega.DoesNotExist:
        # No hay registro de bodega para esta presentación
        pass

# Variables globales para evitar recursión
_processing_cliente_payment = False

# Variables globales para rastrear saldos de transferencias
_transferencias_cliente_saldos = {}

def calcular_saldo_transferencia_cliente(transferencia):
    """Calcula el saldo disponible para una transferencia específica de cliente"""
    global _transferencias_cliente_saldos
    
    if transferencia.id in _transferencias_cliente_saldos:
        return _transferencias_cliente_saldos[transferencia.id]
    return 0

# ---------- LÓGICA PARA CLIENTES ----------
def reevaluar_pagos_cliente(cliente):
    """Resetea y reevalúa todos los pagos de un cliente siguiendo la lógica avanzada de reevaluar_pagos_exportador"""
    global _processing_cliente_payment, _transferencias_cliente_saldos
    
    # Evitar recursión
    if _processing_cliente_payment:
        return
    
    _processing_cliente_payment = True
    try:
        # Usar transaction.atomic para asegurar integridad en la base de datos
        with transaction.atomic():
            # Limpiar el diccionario de saldos
            _transferencias_cliente_saldos = {}
            
            # Obtener todas las transferencias ordenadas cronológicamente
            transferencias = list(TranferenciasCliente.objects.filter(
                cliente=cliente
            ).order_by('fecha_transferencia', 'id'))
            
            # Calcular el total de transferencias
            total_transferencias = sum(t.valor_transferencia for t in transferencias)
            
            # Marcar todas las Ventas como no pagados inicialmente y reiniciar montos pendientes en una sola consulta
            Venta.objects.filter(cliente=cliente).update(
                pagado=False,
                monto_pendiente=0
            )
            
            # Identificar y marcar como pagadas las ventas donde el valor total de factura es igual al abono
            Venta.objects.filter(
                cliente=cliente,
                valor_total_factura_euro__gt=0,
                valor_total_factura_euro=F('valor_total_abono_euro')
            ).update(
                pagado=True,
                monto_pendiente=0
            )
            
            # Marcar ventas sin valor como pagadas
            Venta.objects.filter(
                cliente=cliente,
                valor_total_factura_euro=0
            ).update(
                pagado=True,
                monto_pendiente=0
            )
            
            # Obtener todas las ventas en una sola consulta, ordenadas por fecha
            ventas = list(Venta.objects.filter(
                cliente=cliente
            ).order_by('fecha_entrega'))
            
            # Filtrar las ventas para excluir las que ya están marcadas como pagadas
            ventas = [venta for venta in ventas if not venta.pagado]
            
            # Calcular monto total original de cada venta (para mostrar correctamente los montos pendientes)
            for venta in ventas:
                # El monto original es el valor total de la factura menos el valor del abono
                venta.monto_original = venta.valor_total_factura_euro
                if venta.valor_total_abono_euro:
                    venta.monto_original -= venta.valor_total_abono_euro
            
            # Agrupar ventas por fecha de entrega
            ventas_por_fecha = {}
            for venta in ventas:
                if venta.fecha_entrega not in ventas_por_fecha:
                    ventas_por_fecha[venta.fecha_entrega] = []
                ventas_por_fecha[venta.fecha_entrega].append(venta)
            
            # Variables para rastrear las transferencias disponibles
            total_disponible = total_transferencias
            fondos_usados = Decimal('0.0')
            
            # Ordenar las fechas cronológicamente
            fechas_ordenadas = sorted(ventas_por_fecha.keys())
            
            # Listas para acumular ventas a actualizar en lote
            ventas_pagadas = []
            ventas_pendientes = []
            
            # Copia de las transferencias para rastrear saldos
            for t in transferencias:
                _transferencias_cliente_saldos[t.id] = t.valor_transferencia
            
            # Procesar todas las ventas en orden cronológico
            for fecha in fechas_ordenadas:
                ventas_del_dia = ventas_por_fecha[fecha]
                
                for venta in ventas_del_dia:
                    # Usar el valor total de la factura menos el valor del abono
                    monto_pagar = venta.monto_original
                    
                    if monto_pagar <= 0:
                        continue  # Si no hay que pagar nada, continuar con la siguiente venta
                    
                    # Determinar cuánto podemos pagar con los fondos disponibles
                    fondos_disponibles = sum(_transferencias_cliente_saldos.values())
                    monto_a_pagar = min(monto_pagar, fondos_disponibles)
                    
                    if monto_a_pagar > 0:
                        # Rastrear los fondos utilizados
                        fondos_usados += monto_a_pagar
                        monto_restante = monto_a_pagar
                        
                        # Usar transferencias en orden cronológico
                        for transferencia in transferencias:
                            if monto_restante <= 0:
                                break
                                
                            # Verificar saldo disponible de esta transferencia
                            saldo_transferencia = _transferencias_cliente_saldos.get(transferencia.id, 0)
                            
                            if saldo_transferencia <= 0:
                                continue
                                
                            # Calcular cuánto usar de esta transferencia
                            monto_usado = min(monto_restante, saldo_transferencia)
                            
                            if monto_usado > 0:
                                # Actualizar saldo de la transferencia
                                _transferencias_cliente_saldos[transferencia.id] = saldo_transferencia - monto_usado
                                monto_restante -= monto_usado
                        
                        # Calcular el monto restante por pagar
                        monto_pendiente = monto_pagar - monto_a_pagar
                        
                        # Actualizar la venta
                        if monto_pendiente == 0:
                            # Completamente pagada
                            venta.pagado = True
                            venta.monto_pendiente = 0
                            ventas_pagadas.append(venta)
                        else:
                            # Parcialmente pagada
                            venta.pagado = False
                            venta.monto_pendiente = monto_pendiente
                            ventas_pendientes.append(venta)
                    else:
                        # No hay fondos disponibles para esta venta
                        venta.pagado = False
                        venta.monto_pendiente = monto_pagar
                        ventas_pendientes.append(venta)
            
            # Realizar actualizaciones en lote
            if ventas_pagadas:
                Venta.objects.bulk_update(
                    ventas_pagadas,
                    ['pagado', 'monto_pendiente']
                )
            
            if ventas_pendientes:
                Venta.objects.bulk_update(
                    ventas_pendientes,
                    ['pagado', 'monto_pendiente']
                )
            
            # Verificar si hay ventas pendientes
            hay_ventas_pendientes = any(not venta.pagado for venta in ventas)
            
            # Calcular saldo final para el balance
            saldo_final = Decimal('0.0')
            
            # Solo mostrar saldo positivo si no hay ventas pendientes
            if not hay_ventas_pendientes:
                saldo_final = total_disponible - fondos_usados
            
            # Actualizar el balance del cliente
            balance, created = BalanceCliente.objects.get_or_create(
                cliente=cliente,
                defaults={'saldo_disponible': saldo_final}
            )
            if not created:
                balance.saldo_disponible = saldo_final
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

# Añadir signals para DetalleVenta que aseguren la actualización de los totales de la venta
@receiver(post_save, sender=DetalleVenta)
def actualizar_venta_tras_modificar_detalle(sender, instance, created, **kwargs):
    """Asegura que los totales de la venta se actualicen cuando se modifica un detalle"""
    global _processing_cliente_payment
    if _processing_cliente_payment:
        return
    
    # Ejecutar en una transacción para garantizar consistencia
    with transaction.atomic():
        if instance.venta and hasattr(instance.venta, 'cliente'):
            # La actualización de los totales ya ocurre en el método save de DetalleVenta
            # Recuperar la venta actual para asegurar tener los datos actualizados
            venta_actual = Venta.objects.get(pk=instance.venta.pk)
            cliente = venta_actual.cliente
            
            # Después tenemos que reevaluar los pagos del cliente
            # La reevaluación debe hacerse después de asegurar que todos los cálculos
            # y actualizaciones en la venta estén completados
            reevaluar_pagos_cliente(cliente)

@receiver(post_delete, sender=DetalleVenta)
def actualizar_venta_tras_eliminar_detalle(sender, instance, **kwargs):
    """Asegura que los totales de la venta se actualicen cuando se elimina un detalle"""
    global _processing_cliente_payment
    if _processing_cliente_payment:
        return
        
    # Intentar obtener el ID de la venta y su cliente
    venta_id = getattr(instance, 'venta_id', None)
    
    if venta_id:
        try:
            # Ejecutar en una transacción para garantizar consistencia
            with transaction.atomic():
                # Obtener la venta directamente con select_related para eficiencia
                venta = Venta.objects.select_related('cliente').get(pk=venta_id)
                
                # La actualización de los totales ya ocurre en el método delete de DetalleVenta
                # Refrescar la venta para asegurar tener los datos actualizados
                venta.refresh_from_db()
                
                # Reevaluar los pagos del cliente
                reevaluar_pagos_cliente(venta.cliente)
        except Venta.DoesNotExist:
            # Si la venta no existe, no hay necesidad de actualizar
            pass

# Añadir un signal específico para recalcular totales de venta cuando cambian los detalles
@receiver([post_save, post_delete], sender=DetalleVenta)
def asegurar_actualizacion_completa_venta(sender, instance, **kwargs):
    """
    Signal adicional para garantizar que todos los totales de venta están actualizados
    después de cualquier cambio en DetalleVenta
    """
    # Identificar la venta relacionada
    venta_id = None
    if hasattr(instance, 'venta_id'):
        venta_id = instance.venta_id
    
    if venta_id:
        try:
            # Intentar obtener la venta y actualizar sus campos calculados
            with transaction.atomic():
                # Recalcular totales mediante agregación
                from django.db.models import Sum, F
                
                # Obtener totales actualizados
                totales = DetalleVenta.objects.filter(venta_id=venta_id).aggregate(
                    total_producto=Coalesce(Sum('valor_x_producto'), Decimal('0')),
                    total_abono=Coalesce(Sum('valor_abono_euro'), Decimal('0')),
                    total_cajas=Coalesce(Sum('cajas_enviadas'), 0)
                )
                
                # Actualizar la venta directamente
                subtotal = totales['total_producto']
                iva_amount = subtotal * Decimal('0.04')  # 4% IVA
                
                # Actualizar todos los campos relevantes
                Venta.objects.filter(pk=venta_id).update(
                    subtotal_factura=subtotal,
                    valor_total_abono_euro=totales['total_abono'],
                    iva=iva_amount,
                    valor_total_factura_euro=subtotal + iva_amount,
                    total_cajas_pedido=totales['total_cajas']
                )
        except Exception as e:
            # Log el error pero no causar fallos en la aplicación
            print(f"Error actualizando totales de venta: {e}")

