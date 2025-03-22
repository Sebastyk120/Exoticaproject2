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

@receiver(post_save, sender=DetallePedido)
def actualizar_stock_bodega(sender, instance, created, **kwargs):
    presentacion = instance.presentacion
    
    # Obtener o crear el registro en bodega para esta presentación
    bodega, created_bodega = Bodega.objects.get_or_create(presentacion=presentacion)
    
    # Calcular el stock total sumando todas las cajas recibidas para esta presentación
    resultado = DetallePedido.objects.filter(
        presentacion=presentacion
    ).aggregate(total_cajas=Sum('cajas_recibidas'))
    
    total_cajas = resultado['total_cajas'] or 0
    
    # Asegurar que total_cajas es un entero
    bodega.stock_actual = int(total_cajas)
    bodega.save()

@receiver(post_delete, sender=DetallePedido)
def actualizar_stock_bodega_delete(sender, instance, **kwargs):
    presentacion = instance.presentacion
    
    try:
        bodega = Bodega.objects.get(presentacion=presentacion)
        
        # Recalcular el stock total
        resultado = DetallePedido.objects.filter(
            presentacion=presentacion
        ).aggregate(total_cajas=Sum('cajas_recibidas'))
        
        total_cajas = resultado['total_cajas'] or 0
        
        # Asegurar que total_cajas es un entero
        bodega.stock_actual = int(total_cajas)
        bodega.save()
    except Bodega.DoesNotExist:
        # No hay registro de bodega para esta presentación, no es necesario hacer nada
        pass

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
                                trm_suma += transferencia.trm
                                transferencias_count += 1
                        
                        # Calcular el promedio de TRM
                        trm_promedio = Decimal('0.0')
                        if transferencias_count > 0:
                            trm_promedio = trm_suma / transferencias_count
                        
                        # Actualizar el pedido
                        if monto_pendiente == 0:
                            # Completamente pagado
                            pedido.pagado = True
                            pedido.monto_pendiente = 0
                            if trm_promedio > 0:
                                pedido.valor_factura_eur = monto_pagar / trm_promedio
                            pedido.estado_pedido = "Pagado"
                            pedidos_pagados.append(pedido)
                        else:
                            # Parcialmente pagado
                            pedido.pagado = False
                            pedido.monto_pendiente = monto_pendiente
                            if trm_promedio > 0:
                                pedido.valor_factura_eur = monto_a_pagar / trm_promedio
                            pedido.estado_pedido = "En Proceso"
                            pedidos_pendientes.append(pedido)
                    else:
                        # No hay fondos disponibles para este pedido
                        pedido.pagado = False
                        pedido.monto_pendiente = monto_pagar
                        pedido.estado_pedido = "En Proceso"
                        pedidos_pendientes.append(pedido)
            
            # Realizar actualizaciones en lote
            if pedidos_pagados:
                Pedido.objects.bulk_update(
                    pedidos_pagados,
                    ['pagado', 'valor_factura_eur', 'estado_pedido', 'monto_pendiente']
                )
            
            if pedidos_pendientes:
                Pedido.objects.bulk_update(
                    pedidos_pendientes,
                    ['pagado', 'valor_factura_eur', 'estado_pedido', 'monto_pendiente']
                )
            
            # Verificar si hay pedidos pendientes
            hay_pedidos_pendientes = any(not pedido.pagado for pedido in pedidos)
            
            # Calcular saldo final para el balance
            saldo_final = Decimal('0.0')
            
            # Solo mostrar saldo positivo si no hay pedidos pendientes
            if not hay_pedidos_pendientes:
                saldo_final = total_disponible - fondos_usados
            
            # Actualizar el balance del exportador
            BalanceExportador.objects.update_or_create(
                exportador=exportador,
                defaults={'saldo_disponible': saldo_final}
            )
    
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
            
            # Obtener todos los gastos en una sola consulta
            gastos = list(GastosAduana.objects.filter(
                agencia_aduana=agencia_aduana
            ).order_by('id'))  # Orden por ID, podrías usar otra fecha si existe
            
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
            
            # Obtener todos los gastos en una sola consulta
            gastos = list(GastosCarga.objects.filter(
                agencia_carga=agencia_carga
            ).order_by('id'))
            
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

