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
    """
    Actualiza el stock en Bodega cuando se crea o actualiza un DetallePedido.
    El stock se calcula como la suma de todas las cajas_recibidas para una presentación.
    """
    presentacion = instance.presentacion
    
    # Obtener o crear el registro en bodega para esta presentación
    bodega, created_bodega = Bodega.objects.get_or_create(presentacion=presentacion)
    
    # Calcular el stock total sumando todas las cajas recibidas para esta presentación
    resultado = DetallePedido.objects.filter(
        presentacion=presentacion
    ).aggregate(total_cajas=Sum('cajas_recibidas'))
    
    total_cajas = resultado['total_cajas'] or 0
    
    bodega.stock_actual = total_cajas
    bodega.save()

@receiver(post_delete, sender=DetallePedido)
def actualizar_stock_bodega_delete(sender, instance, **kwargs):
    """
    Actualiza el stock en Bodega cuando se elimina un DetallePedido.
    """
    presentacion = instance.presentacion
    
    try:
        bodega = Bodega.objects.get(presentacion=presentacion)
        
        # Recalcular el stock total
        resultado = DetallePedido.objects.filter(
            presentacion=presentacion
        ).aggregate(total_cajas=Sum('cajas_recibidas'))
        
        total_cajas = resultado['total_cajas'] or 0
        
        bodega.stock_actual = total_cajas
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
                        trm_ponderada = Decimal('0.0')
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
                        
                        # Calcular la TRM ponderada para este pago
                        for transferencia, monto_usado in transferencias_usadas:
                            if transferencia.trm:
                                proporcion = monto_usado / monto_a_pagar
                                trm_ponderada += transferencia.trm * proporcion
                        
                        # Actualizar el pedido
                        if monto_pendiente == 0:
                            # Completamente pagado
                            pedido.pagado = True
                            pedido.monto_pendiente = 0
                            if trm_ponderada > 0:
                                pedido.valor_factura_eur = monto_pagar * trm_ponderada
                            pedido.estado_pedido = "Pagado"
                            pedidos_pagados.append(pedido)
                        else:
                            # Parcialmente pagado
                            pedido.pagado = False
                            pedido.monto_pendiente = monto_pendiente
                            if trm_ponderada > 0:
                                pedido.valor_factura_eur = monto_a_pagar * trm_ponderada
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
    
    # Evitar recursión
    if _processing_aduana_payment:
        return
    
    _processing_aduana_payment = True
    try:
        total_transferencias = TranferenciasAduana.objects.filter(
            agencia_aduana=agencia_aduana
        ).aggregate(total=Sum('valor_transferencia'))['total'] or Decimal('0.0')
        
        gastos = GastosAduana.objects.filter(
            agencia_aduana=agencia_aduana
        ).order_by('id')  # Orden por ID, podrías usar otra fecha si existe
        
        # Marcar todos los gastos como no pagados inicialmente
        GastosAduana.objects.filter(agencia_aduana=agencia_aduana).update(pagado=False)
        
        saldo_disponible = total_transferencias
        gastos_pagados_ids = []
        
        # Procesar gastos secuencialmente
        continuar_procesando = True
        for gasto in gastos:
            if not continuar_procesando:
                break
                
            monto_pagar = gasto.valor_gastos_aduana
            if gasto.valor_nota_credito:
                monto_pagar -= gasto.valor_nota_credito
            
            if saldo_disponible >= monto_pagar:
                saldo_disponible -= monto_pagar
                gastos_pagados_ids.append(gasto.pk)
            else:
                # Si no hay suficiente saldo para este gasto, detenemos el procesamiento
                continuar_procesando = False

        # Marcar como pagados los gastos que se pudieron cubrir
        if gastos_pagados_ids:
            GastosAduana.objects.filter(pk__in=gastos_pagados_ids).update(pagado=True)

        # Actualizar el balance de la agencia de aduana
        balance, created = BalanceGastosAduana.objects.get_or_create(agencia_aduana=agencia_aduana)
        balance.saldo_disponible = saldo_disponible
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
        # Obtener todas las transferencias ordenadas cronológicamente
        transferencias = TranferenciasCarga.objects.filter(
            agencia_carga=agencia_carga
        ).order_by('fecha_transferencia', 'id')
        
        # Calcular el total de transferencias 
        total_transferencias = sum(t.valor_transferencia for t in transferencias)
        
        gastos = GastosCarga.objects.filter(
            agencia_carga=agencia_carga
        ).order_by('id')  # Orden por ID, podrías usar otra fecha si existe
        
        # Marcar todos los gastos como no pagados inicialmente
        GastosCarga.objects.filter(agencia_carga=agencia_carga).update(pagado=False, valor_gastos_carga_eur=0)
        
        saldo_disponible = Decimal('0.0')
        idx_transferencia = 0  # Índice de la transferencia actual
        
        # Procesar gastos secuencialmente
        for gasto in gastos:
            # Calcular monto a pagar, restando notas de crédito si existen
            monto_pagar = gasto.valor_gastos_carga
            
            # Simplemente verificar si valor_nota_credito tiene un valor
            if gasto.valor_nota_credito:
                monto_pagar -= gasto.valor_nota_credito
            
            if monto_pagar <= 0:
                continue  # Si no hay que pagar nada, continuar con el siguiente gasto
            
            # Variables para calcular la TRM ponderada
            trm_ponderada = Decimal('0.0')
            monto_pagado_total = Decimal('0.0')
            
            # Verificar si podemos pagar este gasto con las transferencias disponibles
            monto_restante = monto_pagar
            transferencias_usadas = []  # Lista de tuplas (transferencia, monto_usado)
            
            while monto_restante > 0 and idx_transferencia < len(transferencias):
                transferencia_actual = transferencias[idx_transferencia]
                
                # Determinar cuánto podemos usar de esta transferencia
                if saldo_disponible == 0:
                    # Si no hay saldo de transferencias anteriores, usamos esta transferencia
                    monto_disponible = transferencia_actual.valor_transferencia
                else:
                    # Si ya teníamos saldo de transferencias anteriores
                    monto_disponible = saldo_disponible
                    
                monto_usado = min(monto_restante, monto_disponible)
                
                if monto_usado > 0:
                    # Registrar cuánto se usó de esta transferencia
                    transferencias_usadas.append((transferencia_actual, monto_usado))
                    
                    # Actualizar montos
                    monto_restante -= monto_usado
                    
                    # Actualizar el saldo disponible
                    if saldo_disponible >= monto_usado:
                        saldo_disponible -= monto_usado
                    else:
                        # Consumimos de la transferencia actual
                        saldo_disponible = transferencia_actual.valor_transferencia - monto_usado
                        idx_transferencia += 1
                else:
                    # Pasar a la siguiente transferencia si esta no tiene fondos
                    idx_transferencia += 1
                    saldo_disponible = transferencia_actual.valor_transferencia
            
            # Después de procesar todas las transferencias para este gasto
            if monto_restante == 0:
                # Calcular la TRM ponderada para este gasto
                for transferencia, monto_usado in transferencias_usadas:
                    if transferencia.trm:
                        # Calcular la proporción que esta transferencia cubre del total
                        proporcion = monto_usado / monto_pagar
                        # Acumular la TRM ponderada
                        trm_ponderada += transferencia.trm * proporcion
                        monto_pagado_total += monto_usado
                
                # Actualizar el gasto como pagado y con su valor en EUR calculado
                gasto.pagado = True
                if trm_ponderada > 0:
                    gasto.valor_gastos_carga_eur = monto_pagar * trm_ponderada
                gasto.save()
        
        # Actualizar el balance de la agencia de carga
        balance, created = BalanceGastosCarga.objects.get_or_create(agencia_carga=agencia_carga)
        
        # Calcular saldo final sumando el saldo disponible de la última transferencia
        # y cualquier transferencia restante
        saldo_final = saldo_disponible
        for i in range(idx_transferencia, len(transferencias)):
            saldo_final += transferencias[i].valor_transferencia
            
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
    """
    Actualiza los pagos del exportador cuando se crea o modifica un DetallePedido.
    """
    global _processing_exportador_payment
    if _processing_exportador_payment:
        return
        
    if hasattr(instance, 'pedido') and instance.pedido and hasattr(instance.pedido, 'exportador'):
        reevaluar_pagos_exportador(instance.pedido.exportador)

@receiver(post_delete, sender=DetallePedido)
def actualizar_pagos_exportador_tras_eliminar_detalle(sender, instance, **kwargs):
    """
    Actualiza los pagos del exportador cuando se elimina un DetallePedido.
    """
    if hasattr(instance, 'pedido') and instance.pedido and hasattr(instance.pedido, 'exportador'):
        reevaluar_pagos_exportador(instance.pedido.exportador)

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

