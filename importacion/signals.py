from django.db.models.functions import Coalesce
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum, F, Value
from django.db import transaction
from decimal import Decimal

from .models import (
    DetallePedido, Bodega, Pedido, TranferenciasExportador, BalanceExportador,
    GastosAduana, TranferenciasAduana, BalanceGastosAduana,
    GastosCarga, TranferenciasCarga, BalanceGastosCarga
)

# Función utilitaria para actualizar el stock de múltiples presentaciones a la vez
def actualizar_stock_multiple(presentaciones_ids):
    """
    Actualiza el stock de varias presentaciones de manera eficiente en una sola operación.
    Útil para operaciones por lotes donde múltiples productos pueden haberse modificado.
    """
    global _actualizando_inventario
    
    if _actualizando_inventario:
        return
    
    if not presentaciones_ids:
        return
        
    try:
        _actualizando_inventario = True
        
        with transaction.atomic():
            from comercial.models import DetalleVenta
            from productos.models import Presentacion
            from django.db.models.functions import Coalesce
            
            for presentacion_id in presentaciones_ids:
                try:
                    presentacion = Presentacion.objects.get(id=presentacion_id)
                    
                    # Paso 1: Calcular entradas (cajas recibidas en todos los pedidos)
                    entradas = DetallePedido.objects.filter(
                        presentacion=presentacion
                    ).aggregate(
                        total_cajas=Coalesce(Sum('cajas_recibidas'), 0)
                    )['total_cajas'] or 0
                    
                    # Paso 2: Calcular salidas (cajas enviadas en todas las ventas)
                    salidas = DetalleVenta.objects.filter(
                        presentacion=presentacion
                    ).aggregate(
                        total_cajas=Coalesce(Sum('cajas_enviadas'), 0)
                    )['total_cajas'] or 0
                    
                    # Paso 3: Calcular stock actual (entradas - salidas)
                    stock_actual = max(0, int(entradas - salidas))
                    
                    # Paso 4: Actualizar o crear registro en bodega
                    bodega, created = Bodega.objects.get_or_create(
                        presentacion=presentacion,
                        defaults={'stock_actual': stock_actual}
                    )
                    
                    # Paso 5: Actualizar el registro si ya existe
                    if not created:
                        bodega.stock_actual = stock_actual
                        bodega.save(update_fields=['stock_actual', 'ultima_actualizacion'])
                    
                    # Registrar operación para depuración
                    import logging
                    logger = logging.getLogger('importacion')
                    logger.info(f"Stock recalculado para {presentacion}: Entradas={entradas}, Salidas={salidas}, Stock actual={stock_actual}")
                    
                except Exception as e:
                    import logging
                    logger = logging.getLogger('importacion')
                    logger.error(f"Error al actualizar stock de presentación {presentacion_id}: {e}")
    
    finally:
        _actualizando_inventario = False

@receiver(post_save, sender=DetallePedido)
def actualizar_stock_bodega(sender, instance, created, **kwargs):
    """
    Actualiza el stock en Bodega cuando se crea o actualiza un DetallePedido.
    Si se especifica _skip_stock_update, la actualización se omite.
    """
    global _actualizando_inventario
    
    # Evitar recursión o actualizaciones redundantes
    if _actualizando_inventario or getattr(instance, '_skip_stock_update', False):
        return

    # Verificar si realmente hubo un cambio en cajas_recibidas
    if not created and hasattr(instance, '_original_cajas_recibidas'):
        if instance._original_cajas_recibidas == instance.cajas_recibidas and instance._original_presentacion_id == instance.presentacion_id:
            # No hubo cambio en la cantidad de cajas ni en la presentación, no actualizar el stock
            return
    
    try:
        _actualizando_inventario = True
        
        # Actualizar el stock usando el método mejorado que considera las ventas
        actualizar_stock_multiple([instance.presentacion_id])
        
        # Si hubo cambio de presentación, también actualizar la presentación anterior
        if hasattr(instance, '_original_presentacion_id') and instance._original_presentacion_id and instance._original_presentacion_id != instance.presentacion_id:
            actualizar_stock_multiple([instance._original_presentacion_id])
    
    finally:
        _actualizando_inventario = False

# Variable global para controlar actualizaciones en curso
_actualizando_inventario = False

@receiver(post_save, sender=DetallePedido)
def actualizar_stock_bodega(sender, instance, created, **kwargs):
    """
    Actualiza el stock en Bodega cuando se crea o actualiza un DetallePedido.
    Si se especifica _skip_stock_update, la actualización se omite.
    """
    global _actualizando_inventario
    
    # Evitar recursión o actualizaciones redundantes
    if _actualizando_inventario or getattr(instance, '_skip_stock_update', False):
        return

    # Verificar si realmente hubo un cambio en cajas_recibidas
    if not created and hasattr(instance, '_original_cajas_recibidas'):
        if instance._original_cajas_recibidas == instance.cajas_recibidas:
            # No hubo cambio en la cantidad de cajas, no actualizar el stock
            return
    
    try:
        _actualizando_inventario = True
        
        # Identificar la presentación afectada
        presentacion = instance.presentacion
        
        # Actualizar stock para esta presentación usando una única consulta de suma
        with transaction.atomic():
            # Obtener o crear el registro en bodega
            bodega, created_bodega = Bodega.objects.get_or_create(
                presentacion=presentacion, 
                defaults={'stock_actual': 0}
            )
            
            # Recalcular el stock total
            resultado = DetallePedido.objects.filter(
                presentacion=presentacion
            ).aggregate(total_cajas=Sum('cajas_recibidas'))
            total_cajas = resultado['total_cajas'] or 0
            
            # Actualizar el registro en bodega con el valor total calculado
            bodega.stock_actual = int(total_cajas)
            
            # Guardar en base de datos
            bodega.save(update_fields=['stock_actual', 'ultima_actualizacion'])
            
            # Registrar la operación para depuración
            import logging
            logger = logging.getLogger('importacion')
            if created:
                logger.info(f"Stock actualizado (nuevo): {presentacion} - Total: {total_cajas}")
            else:
                original = getattr(instance, '_original_cajas_recibidas', 0) 
                nuevo = instance.cajas_recibidas or 0
                diferencia = nuevo - original
                logger.info(f"Stock actualizado (edición): {presentacion} - Diferencia: {diferencia}, Nuevo total: {total_cajas}")
    
    finally:
        _actualizando_inventario = False


@receiver(post_delete, sender=DetallePedido)
def actualizar_stock_bodega_delete(sender, instance, **kwargs):
    """
    Actualiza el stock en Bodega cuando se elimina un DetallePedido.
    Usa el mismo método que post_save para garantizar consistencia.
    """
    global _actualizando_inventario
    
    if _actualizando_inventario:
        return
    
    try:
        _actualizando_inventario = True
        
        presentacion = instance.presentacion
        
        with transaction.atomic():
            try:
                # Recalcular stock total
                resultado = DetallePedido.objects.filter(
                    presentacion=presentacion
                ).aggregate(total_cajas=Sum('cajas_recibidas'))
                
                total_cajas = resultado['total_cajas'] or 0
                
                # Actualizar o crear registro en bodega
                bodega, created = Bodega.objects.get_or_create(
                    presentacion=presentacion,
                    defaults={'stock_actual': 0}
                )
                
                # Actualizar stock
                bodega.stock_actual = int(total_cajas)
                bodega.save(update_fields=['stock_actual', 'ultima_actualizacion'])
                
                # Registrar la operación para depuración
                import logging
                logger = logging.getLogger('importacion')
                logger.info(f"Stock actualizado (eliminación): {presentacion} - Cajas eliminadas: {instance.cajas_recibidas}, Nuevo total: {total_cajas}")
            
            except Exception as e:
                import logging
                logger = logging.getLogger('importacion')
                logger.error(f"Error al actualizar stock tras eliminación: {e}")
    finally:
        _actualizando_inventario = False


# Función utilitaria para actualizar el stock de múltiples presentaciones a la vez
def actualizar_stock_multiple(presentaciones_ids):
    """
    Actualiza el stock de varias presentaciones de manera eficiente en una sola operación.
    Útil para operaciones por lotes donde múltiples productos pueden haberse modificado.
    """
    global _actualizando_inventario
    
    if _actualizando_inventario:
        return
    
    if not presentaciones_ids:
        return
        
    try:
        _actualizando_inventario = True
        
        with transaction.atomic():
            from comercial.models import DetalleVenta
            from productos.models import Presentacion
            from django.db.models.functions import Coalesce
            
            for presentacion_id in presentaciones_ids:
                try:
                    presentacion = Presentacion.objects.get(id=presentacion_id)
                    
                    # Paso 1: Calcular entradas (cajas recibidas en todos los pedidos)
                    entradas = DetallePedido.objects.filter(
                        presentacion=presentacion
                    ).aggregate(
                        total_cajas=Coalesce(Sum('cajas_recibidas'), 0)
                    )['total_cajas'] or 0
                    
                    # Paso 2: Calcular salidas (cajas enviadas en todas las ventas)
                    salidas = DetalleVenta.objects.filter(
                        presentacion=presentacion
                    ).aggregate(
                        total_cajas=Coalesce(Sum('cajas_enviadas'), 0)
                    )['total_cajas'] or 0
                    
                    # Paso 3: Calcular stock actual (entradas - salidas)
                    stock_actual = max(0, int(entradas - salidas))
                    
                    # Paso 4: Actualizar o crear registro en bodega
                    bodega, created = Bodega.objects.get_or_create(
                        presentacion=presentacion,
                        defaults={'stock_actual': stock_actual}
                    )
                    
                    # Paso 5: Actualizar el registro si ya existe
                    if not created:
                        bodega.stock_actual = stock_actual
                        bodega.save(update_fields=['stock_actual', 'ultima_actualizacion'])
                    
                    # Registrar operación para depuración
                    import logging
                    logger = logging.getLogger('importacion')
                    logger.info(f"Stock recalculado para {presentacion}: Entradas={entradas}, Salidas={salidas}, Stock actual={stock_actual}")
                    
                except Exception as e:
                    import logging
                    logger = logging.getLogger('importacion')
                    logger.error(f"Error al actualizar stock de presentación {presentacion_id}: {e}")
    
    finally:
        _actualizando_inventario = False


# Variables globales para evitar recursión
_processing_exportador_payment = False
_processing_aduana_payment = False
_processing_carga_payment = False

# Variables globales para rastrear saldos de transferencias
_transferencias_saldos = {}


def calcular_saldo_transferencia(transferencia):
    """Calcula el saldo disponible para una transferencia específica"""
    global _transferencias_saldos

    if transferencia.id in _transferencias_saldos:
        return _transferencias_saldos[transferencia.id]
    return 0


# ---------- LÓGICA PARA EXPORTADOR ----------

def reevaluar_pagos_exportador(exportador):
    """Resetea y reevalúa todos los pagos de un exportador"""
    global _processing_exportador_payment, _transferencias_saldos

    # Evitar recursión
    if _processing_exportador_payment:
        return

    _processing_exportador_payment = True
    try:
        # Usar transaction.atomic para asegurar que todas las operaciones se completen o ninguna
        with transaction.atomic():
            # Limpiar el diccionario de saldos
            _transferencias_saldos = {}

            # Obtener todas las transferencias ordenadas cronológicamente en una sola consulta
            transferencias = list(TranferenciasExportador.objects.filter(
                exportador=exportador
            ).order_by('fecha_transferencia', 'id'))

            # Marcar todos los pedidos como no pagados inicialmente y reiniciar montos pendientes en una sola consulta
            Pedido.objects.filter(exportador=exportador).update(
                pagado=False,
                valor_factura_eur=None,
                monto_pendiente=0,
                estado_pedido="En Proceso"
            )

            # Identificar y marcar como pagados los pedidos donde valor_total_factura_usd = valor_total_nc_usd
            Pedido.objects.filter(
                exportador=exportador,
                valor_total_factura_usd__gt=0,
                valor_total_factura_usd=F('valor_total_nc_usd')
            ).update(
                pagado=True,
                monto_pendiente=0,
                estado_pedido="Pagado"
            )
            # Aqui marco los pedidos que estan en 0 o sin Detalles
            Pedido.objects.filter(
                exportador=exportador,
                valor_total_factura_usd=0
            ).update(
                pagado=True,
                monto_pendiente=0,
                estado_pedido="Pagado"
            )

            # Obtener todos los pedidos en una sola consulta, ordenados por fecha
            pedidos = list(Pedido.objects.filter(
                exportador=exportador
            ).order_by('fecha_entrega'))

            # Filtrar los pedidos para excluir los que ya están marcados como pagados
            pedidos = [pedido for pedido in pedidos if not pedido.pagado]

            # Calcular monto total original de cada pedido (para mostrar correctamente los montos pendientes)
            for pedido in pedidos:
                pedido.monto_original = pedido.valor_total_factura_usd - pedido.valor_total_nc_usd

            # Agrupar pedidos por fecha de entrega
            pedidos_por_fecha = {}
            for pedido in pedidos:
                if pedido.fecha_entrega not in pedidos_por_fecha:
                    pedidos_por_fecha[pedido.fecha_entrega] = []
                pedidos_por_fecha[pedido.fecha_entrega].append(pedido)

            # Variables para rastrear las transferencias disponibles
            total_disponible = sum(t.valor_transferencia for t in transferencias)
            fondos_usados = Decimal('0.0')

            # Ordenar las fechas cronológicamente
            fechas_ordenadas = sorted(pedidos_por_fecha.keys())

            # Listas para acumular pedidos a actualizar en lote
            pedidos_pagados = []
            pedidos_pendientes = []

            # Procesar todos los pedidos en orden cronológico
            for fecha in fechas_ordenadas:
                pedidos_del_dia = pedidos_por_fecha[fecha]

                for pedido in pedidos_del_dia:
                    # Usar el valor total de la factura menos el valor de la nota de crédito
                    monto_pagar = pedido.monto_original

                    if monto_pagar <= 0:
                        continue  # Si no hay que pagar nada, continuar con el siguiente pedido

                    # Determinar cuánto podemos pagar con los fondos disponibles
                    fondos_disponibles = total_disponible - fondos_usados
                    monto_a_pagar = min(monto_pagar, fondos_disponibles)

                    if monto_a_pagar > 0:
                        # Rastrear los fondos utilizados
                        fondos_usados += monto_a_pagar

                        # Calcular el monto restante por pagar
                        monto_pendiente = monto_pagar - monto_a_pagar

                        # Variables para calcular la TRM ponderada
                        trm_suma = Decimal('0.0')
                        transferencias_count = 0
                        transferencias_usadas = []

                        # Determinar qué transferencias se usan para este pago
                        saldo_temp = Decimal('0.0')
                        monto_restante = monto_a_pagar

                        for transferencia in transferencias:
                            if monto_restante <= 0:
                                break

                            # Verificar si ya se usó completamente esta transferencia
                            if transferencia.id in _transferencias_saldos:
                                saldo_transferencia = _transferencias_saldos[transferencia.id]
                            else:
                                saldo_transferencia = transferencia.valor_transferencia

                            if saldo_transferencia <= 0:
                                continue

                            monto_usado = min(monto_restante, saldo_transferencia)
                            if monto_usado > 0:
                                transferencias_usadas.append((transferencia, monto_usado))
                                monto_restante -= monto_usado

                                # Actualizar el saldo de esta transferencia
                                _transferencias_saldos[transferencia.id] = saldo_transferencia - monto_usado

                        # Calcular el promedio de TRM para las transferencias usadas
                        for transferencia, monto_usado in transferencias_usadas:
                            if transferencia.trm:
                                trm_suma += transferencia.trm * (monto_usado / monto_a_pagar)
                                transferencias_count += 1

                        # Si no hay transferencias con TRM registrada, usar un valor predeterminado o dejarlo en None
                        trm_ponderada = None
                        if transferencias_count > 0 and trm_suma > 0:
                            trm_ponderada = trm_suma

                            # Calcular el valor en EUR utilizando la TRM ponderada
                            valor_factura_eur = (monto_a_pagar / trm_ponderada).quantize(Decimal('0.01'))
                        else:
                            valor_factura_eur = None

                        # Actualizar el estado del pedido según si está totalmente pagado o parcialmente pagado
                        if monto_pendiente <= 0:
                            # Pedido totalmente pagado
                            pedido.pagado = True
                            pedido.estado_pedido = "Pagado"
                            pedido.monto_pendiente = Decimal('0.0')
                            pedido.valor_factura_eur = valor_factura_eur
                            pedidos_pagados.append(pedido)
                        else:
                            # Pedido parcialmente pagado
                            pedido.pagado = False
                            pedido.estado_pedido = "Pago Parcial"
                            pedido.monto_pendiente = monto_pendiente
                            pedido.valor_factura_eur = valor_factura_eur
                            pedidos_pendientes.append(pedido)
                    else:
                        # No hay fondos suficientes para pagar este pedido
                        pedido.pagado = False
                        pedido.estado_pedido = "En Proceso"
                        pedido.monto_pendiente = monto_pagar
                        pedido.valor_factura_eur = None
                        pedidos_pendientes.append(pedido)

            # Actualizar pedidos en lote
            # Después de marcar todos los pedidos, actualizar cada uno para calcular el valor_x_producto_eur en sus detalles
            for pedido in pedidos_pagados + pedidos_pendientes:
                pedido.save(update_fields=['pagado', 'estado_pedido', 'monto_pendiente', 'valor_factura_eur'])

                # Para los pedidos marcados como pagados, actualizar los detalles llamando a la función en DetallePedido
                from importacion.models import DetallePedido
                if pedido.pagado:
                    DetallePedido.actualizar_totales_pedido(pedido.id)

            # Actualizar el balance del exportador
            balance, created = BalanceExportador.objects.get_or_create(exportador=exportador)
            balance.saldo_disponible = total_disponible - fondos_usados
            balance.save()

    finally:
        _processing_exportador_payment = False


# ---------- LÓGICA PARA AGENCIA DE ADUANA ----------

def reevaluar_pagos_aduana(agencia_aduana):
    """Resetea y reevalúa todos los pagos de una agencia de aduana"""
    global _processing_aduana_payment

    if _processing_aduana_payment:
        return

    _processing_aduana_payment = True
    try:
        # Usar transaction.atomic para asegurar que todas las operaciones se completen o ninguna
        with transaction.atomic():
            # Obtener todas las transferencias ordenadas cronológicamente
            transferencias = TranferenciasAduana.objects.filter(
                agencia_aduana=agencia_aduana
            ).order_by('fecha_transferencia', 'id')

            # Calcular el total de transferencias
            total_transferencias = sum(t.valor_transferencia for t in transferencias)

            # Marcar todos los gastos como no pagados inicialmente y reiniciar montos pendientes
            GastosAduana.objects.filter(agencia_aduana=agencia_aduana).update(
                pagado=False,
                monto_pendiente=0
            )

            # Obtener todos los gastos en una sola consulta, ordenados por fecha de entrega de pedidos (más reciente primero)
            gastos = list(GastosAduana.objects.filter(
                agencia_aduana=agencia_aduana
            ).prefetch_related('pedidos').distinct().order_by('-pedidos__fecha_entrega', '-id'))

            # Variables para rastrear
            saldo_disponible = total_transferencias
            gastos_pagados = []
            gastos_pendientes = []

            # Procesar todos los gastos secuencialmente
            for gasto in gastos:
                # Calcular monto a pagar (valor gastos - nota de crédito)
                monto_pagar = gasto.valor_gastos_aduana
                if gasto.valor_nota_credito:
                    monto_pagar -= gasto.valor_nota_credito

                if monto_pagar <= 0:
                    # Si no hay que pagar nada, marcar como pagado
                    gasto.pagado = True
                    gasto.monto_pendiente = 0
                    gastos_pagados.append(gasto)
                    continue

                # Verificar si hay fondos suficientes
                if saldo_disponible >= monto_pagar:
                    # Hay fondos suficientes
                    saldo_disponible -= monto_pagar
                    gasto.pagado = True
                    gasto.monto_pendiente = 0
                    gastos_pagados.append(gasto)
                else:
                    # No hay fondos suficientes
                    if saldo_disponible > 0:
                        # Usar lo que queda de saldo para este gasto
                        gasto.monto_pendiente = monto_pagar - saldo_disponible
                        saldo_disponible = 0
                    else:
                        # No hay saldo disponible
                        gasto.monto_pendiente = monto_pagar

                    gasto.pagado = False
                    gastos_pendientes.append(gasto)

            # Actualizar gastos en lote
            if gastos_pagados:
                GastosAduana.objects.bulk_update(
                    gastos_pagados,
                    ['pagado', 'monto_pendiente']
                )

            if gastos_pendientes:
                GastosAduana.objects.bulk_update(
                    gastos_pendientes,
                    ['pagado', 'monto_pendiente']
                )

            # Verificar si hay gastos pendientes
            hay_gastos_pendientes = bool(gastos_pendientes)

            # Calcular saldo final para el balance
            saldo_final = Decimal('0.0')

            # Solo mostrar saldo positivo si no hay gastos pendientes
            if not hay_gastos_pendientes:
                saldo_final = saldo_disponible

            # Actualizar el balance de la agencia de aduana
            balance, created = BalanceGastosAduana.objects.get_or_create(agencia_aduana=agencia_aduana)
            balance.saldo_disponible = saldo_final
            balance.save()

    finally:
        _processing_aduana_payment = False


# ---------- LÓGICA PARA AGENCIA DE CARGA ----------

def reevaluar_pagos_carga(agencia_carga):
    """Resetea y reevalúa todos los pagos de una agencia de carga"""
    global _processing_carga_payment

    # Evitar recursión
    if _processing_carga_payment:
        return

    _processing_carga_payment = True
    try:
        # Usar transaction.atomic para asegurar que todas las operaciones se completen o ninguna
        with transaction.atomic():
            # Obtener todas las transferencias ordenadas cronológicamente
            transferencias = list(TranferenciasCarga.objects.filter(
                agencia_carga=agencia_carga
            ).order_by('fecha_transferencia', 'id'))

            # Calcular el total de transferencias
            total_transferencias = sum(t.valor_transferencia for t in transferencias)

            # Marcar todos los gastos como no pagados inicialmente y reiniciar montos
            GastosCarga.objects.filter(agencia_carga=agencia_carga).update(
                pagado=False,
                valor_gastos_carga_eur=0,
                monto_pendiente=0
            )

            # Obtener todos los gastos en una sola consulta, ordenados por fecha de entrega de pedidos (más reciente primero)
            gastos = list(GastosCarga.objects.filter(
                agencia_carga=agencia_carga
            ).prefetch_related('pedidos').distinct().order_by('-pedidos__fecha_entrega', '-id'))

            # Copia de las transferencias para rastrear saldos
            transferencias_saldos = {t.id: t.valor_transferencia for t in transferencias}

            # Variables para rastrear
            fondos_usados = Decimal('0.0')
            gastos_pagados = []
            gastos_pendientes = []

            # Procesar todos los gastos secuencialmente
            for gasto in gastos:
                # Calcular monto a pagar (valor gastos - nota de crédito)
                monto_pagar = gasto.valor_gastos_carga
                if gasto.valor_nota_credito:
                    monto_pagar -= gasto.valor_nota_credito

                if monto_pagar <= 0:
                    # Si no hay que pagar nada, marcar como pagado
                    gasto.pagado = True
                    gasto.monto_pendiente = 0
                    gastos_pagados.append(gasto)
                    continue

                # Determinar cuánto podemos pagar con los fondos disponibles
                fondos_disponibles = sum(transferencias_saldos.values())
                monto_a_pagar = min(monto_pagar, fondos_disponibles)

                if monto_a_pagar > 0:
                    # Calcular el monto restante por pagar
                    monto_pendiente = monto_pagar - monto_a_pagar

                    # Variables para calcular EUR directamente
                    total_eur = Decimal('0.0')
                    monto_restante = monto_a_pagar

                    # Usar transferencias en orden cronológico
                    for transferencia in transferencias:
                        if monto_restante <= 0:
                            break

                        # Verificar saldo disponible de esta transferencia
                        saldo_transferencia = transferencias_saldos.get(transferencia.id, 0)

                        if saldo_transferencia <= 0:
                            continue

                        # Calcular cuánto usar de esta transferencia
                        monto_usado = min(monto_restante, saldo_transferencia)

                        if monto_usado > 0:
                            # Actualizar saldo de la transferencia
                            transferencias_saldos[transferencia.id] = saldo_transferencia - monto_usado
                            monto_restante -= monto_usado

                            # Calcular valor en EUR para esta porción según TRM de la transferencia
                            if transferencia.trm and transferencia.trm > 0:
                                # Convertir USD a EUR usando el TRM de esta transferencia
                                eur_porcion = monto_usado / transferencia.trm
                                total_eur += eur_porcion

                    # Actualizar fondos usados para el balance general
                    fondos_usados += monto_a_pagar

                    # Actualizar el gasto
                    if monto_pendiente == 0:
                        # Completamente pagado
                        gasto.pagado = True
                        gasto.monto_pendiente = 0
                        gasto.valor_gastos_carga_eur = total_eur
                        gastos_pagados.append(gasto)
                    else:
                        # Parcialmente pagado
                        gasto.pagado = False
                        gasto.monto_pendiente = monto_pendiente
                        gasto.valor_gastos_carga_eur = total_eur
                        gastos_pendientes.append(gasto)
                else:
                    # No hay fondos disponibles para este gasto
                    gasto.pagado = False
                    gasto.monto_pendiente = monto_pagar
                    gastos_pendientes.append(gasto)

            # Realizar actualizaciones en lote
            if gastos_pagados:
                GastosCarga.objects.bulk_update(
                    gastos_pagados,
                    ['pagado', 'valor_gastos_carga_eur', 'monto_pendiente']
                )

            if gastos_pendientes:
                GastosCarga.objects.bulk_update(
                    gastos_pendientes,
                    ['pagado', 'valor_gastos_carga_eur', 'monto_pendiente']
                )

            # Verificar si hay gastos pendientes
            hay_gastos_pendientes = bool(gastos_pendientes)

            # Calcular saldo final para el balance
            saldo_final = Decimal('0.0')

            # Solo mostrar saldo positivo si no hay gastos pendientes
            if not hay_gastos_pendientes:
                saldo_final = total_transferencias - fondos_usados

            # Actualizar el balance de la agencia de carga
            balance, created = BalanceGastosCarga.objects.get_or_create(agencia_carga=agencia_carga)
            balance.saldo_disponible = saldo_final
            balance.save()

    finally:
        _processing_carga_payment = False


# ---------- SEÑALES PARA EXPORTADOR ----------

@receiver(post_save, sender=TranferenciasExportador)
def actualizar_balance_tras_transferencia_exportador(sender, instance, **kwargs):
    reevaluar_pagos_exportador(instance.exportador)


@receiver(post_delete, sender=TranferenciasExportador)
def actualizar_balance_tras_eliminar_transferencia_exportador(sender, instance, **kwargs):
    reevaluar_pagos_exportador(instance.exportador)


@receiver(post_save, sender=Pedido)
def verificar_pago_tras_crear_o_editar_pedido(sender, instance, created, **kwargs):
    global _processing_exportador_payment
    if (_processing_exportador_payment):
        return

    reevaluar_pagos_exportador(instance.exportador)


@receiver(post_delete, sender=Pedido)
def actualizar_balance_tras_eliminar_pedido(sender, instance, **kwargs):
    reevaluar_pagos_exportador(instance.exportador)


@receiver(post_save, sender=DetallePedido)
def actualizar_pagos_exportador_tras_modificar_detalle(sender, instance, **kwargs):
    global _processing_exportador_payment
    if _processing_exportador_payment:
        return

    if hasattr(instance, 'pedido') and instance.pedido and hasattr(instance.pedido, 'exportador'):
        reevaluar_pagos_exportador(instance.pedido.exportador)


@receiver(post_delete, sender=DetallePedido)
def actualizar_pagos_exportador_tras_eliminar_detalle(sender, instance, **kwargs):
    # Verificar si tenemos acceso al pedido y su exportador
    pedido_id = getattr(instance, 'pedido_id', None)

    if pedido_id:
        # Intentar obtener el pedido directamente de la base de datos
        try:
            pedido = Pedido.objects.select_related('exportador').get(pk=pedido_id)

            # Recalcular los valores del pedido
            # Consulta para campos enteros
            totales_enteros = DetallePedido.objects.filter(pedido_id=pedido_id).aggregate(
                total_cajas_solicitadas=Coalesce(Sum('cajas_solicitadas'), 0),
                total_cajas_recibidas=Coalesce(Sum('cajas_recibidas'), 0)
            )

            # Consulta para campos decimales
            totales_decimales = DetallePedido.objects.filter(pedido_id=pedido_id).aggregate(
                total_factura=Coalesce(Sum('valor_x_producto'), Decimal('0')),
                total_nc=Coalesce(Sum('valor_nc_usd'), Decimal('0'))
            )

            # Actualizar el pedido
            pedido.total_cajas_solicitadas = totales_enteros['total_cajas_solicitadas']
            pedido.total_cajas_recibidas = totales_enteros['total_cajas_recibidas']
            pedido.valor_total_factura_usd = totales_decimales['total_factura']
            pedido.valor_total_nc_usd = totales_decimales['total_nc']
            pedido.save()

            # Reevaluar los pagos del exportador
            if hasattr(pedido, 'exportador') and pedido.exportador:
                reevaluar_pagos_exportador(pedido.exportador)

        except Pedido.DoesNotExist:
            # Si el pedido no existe, no hay necesidad de actualizar
            pass


# ---------- SEÑALES PARA AGENCIA DE ADUANA ----------

@receiver(post_save, sender=TranferenciasAduana)
def actualizar_balance_tras_transferencia_aduana(sender, instance, **kwargs):
    reevaluar_pagos_aduana(instance.agencia_aduana)


@receiver(post_delete, sender=TranferenciasAduana)
def actualizar_balance_tras_eliminar_transferencia_aduana(sender, instance, **kwargs):
    reevaluar_pagos_aduana(instance.agencia_aduana)


@receiver(post_save, sender=GastosAduana)
def verificar_pago_tras_crear_o_editar_gastos_aduana(sender, instance, created, **kwargs):
    global _processing_aduana_payment
    if (_processing_aduana_payment):
        return

    reevaluar_pagos_aduana(instance.agencia_aduana)


@receiver(post_delete, sender=GastosAduana)
def actualizar_balance_tras_eliminar_gastos_aduana(sender, instance, **kwargs):
    reevaluar_pagos_aduana(instance.agencia_aduana)


# ---------- SEÑALES PARA AGENCIA DE CARGA ----------

@receiver(post_save, sender=TranferenciasCarga)
def actualizar_balance_tras_transferencia_carga(sender, instance, **kwargs):
    reevaluar_pagos_carga(instance.agencia_carga)


@receiver(post_delete, sender=TranferenciasCarga)
def actualizar_balance_tras_eliminar_transferencia_carga(sender, instance, **kwargs):
    reevaluar_pagos_carga(instance.agencia_carga)


@receiver(post_save, sender=GastosCarga)
def verificar_pago_tras_crear_o_editar_gastos_carga(sender, instance, created, **kwargs):
    global _processing_carga_payment
    if (_processing_carga_payment):
        return

    reevaluar_pagos_carga(instance.agencia_carga)


@receiver(post_delete, sender=GastosCarga)
def actualizar_balance_tras_eliminar_gastos_carga(sender, instance, **kwargs):
    reevaluar_pagos_carga(instance.agencia_carga)


# Signals to automatically update balances on transferencia changes

@receiver(post_save, sender=TranferenciasExportador)
def update_exportador_balance(sender, instance, **kwargs):
    """Update exporter balance when a transfer is saved or updated"""
    reevaluar_pagos_exportador(instance.exportador)


@receiver(post_delete, sender=TranferenciasExportador)
def delete_exportador_balance(sender, instance, **kwargs):
    """Update exporter balance when a transfer is deleted"""
    reevaluar_pagos_exportador(instance.exportador)

# Similar handlers could be added for Aduana and Carga transfers