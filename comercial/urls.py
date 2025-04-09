from django.urls import path
from . import views_clientes, views_ventas, views_dashboard, views_enviar_correos, views

app_name = 'comercial'

urlpatterns = [
    path('clientes/', views_clientes.clientes_view, name='clientes'),
    path('add_client/', views_clientes.add_client, name='add_client'),
    path('get_client/<int:client_id>/', views_clientes.get_client, name='get_client'),
    path('edit_client/<int:client_id>/', views_clientes.edit_client, name='edit_client'),
    
    path('ventas/', views_ventas.lista_ventas, name='lista_ventas'),
    path('ventas/nueva/', views_ventas.nueva_venta, name='nueva_venta'),
    path('ventas/<int:venta_id>/', views_ventas.detalle_venta, name='detalle_venta'),
    path('ventas/<int:venta_id>/guardar/', views_ventas.guardar_venta, name='guardar_venta'),
    path('ventas/guardar/', views_ventas.guardar_venta, name='guardar_venta'),
    path('ventas/<int:venta_id>/guardar_detalle/<int:detalle_id>/', views_ventas.guardar_detalle, name='guardar_detalle'),
    path('ventas/<int:venta_id>/guardar_detalle/', views_ventas.guardar_detalle, name='guardar_detalle'),
    path('ventas/<int:venta_id>/guardar_detalles_batch/', views_ventas.guardar_detalles_batch, name='guardar_detalles_batch'),
    path('ventas/<int:venta_id>/detalles-json/', views_ventas.obtener_detalles_venta, name='obtener_detalles_venta'),
    path('obtener-precio-presentacion/<int:presentacion_id>/<int:cliente_id>/', views_ventas.obtener_precio_presentacion, name='obtener_precio_presentacion'),
    path('ventas/<int:venta_id>/generar-factura/', views_ventas.generar_factura, name='generar_factura'),
    path('ventas/<int:venta_id>/generar-rectificativa/', views_ventas.generar_rectificativa, name='generar_rectificativa'),
    path('ventas/<int:venta_id>/generar-albaran/', views_ventas.generar_albaran, name='generar_albaran'),
    path('ventas/<int:venta_id>/generar-albaran-cliente/', views_ventas.generar_albaran_cliente, name='generar_albaran_cliente'),
    path('validar-stock/<int:presentacion_id>/<int:cajas_enviadas>/', views_ventas.validar_stock, name='validar_stock'),
    path('estado-cuenta/cliente/<int:cliente_id>/', views_clientes.estado_cuenta_cliente, name='estado_cuenta_cliente'),
    # Añadir la ruta para acceso por token
    path('client-statement/<str:token>/', views_clientes.estado_cuenta_cliente_token, name='estado_cuenta_cliente_token'),
    path('estado-cuenta/cliente/<int:cliente_id>/', views_clientes.estado_cuenta_cliente, name='estado_cuenta_cliente'),
    
    # Nueva ruta directa para acceder a los albaranes (más fácil para JavaScript)
    path('generar_albaran_directo/<int:venta_id>/', views_ventas.generar_albaran, name='generar_albaran_directo'),
    
    # Dashboard URLs
    path('dashboard/utilidades/', views_dashboard.dashboard_utilidades, name='dashboard_utilidades'),
    
    # API endpoints
    path('api/dashboard/resumen-utilidad/', views_dashboard.api_resumen_utilidad, name='api_resumen_utilidad'),
    path('api/dashboard/utilidad-por-semana/', views_dashboard.api_utilidad_por_semana, name='api_utilidad_por_semana'),
    path('api/dashboard/distribucion-costos/', views_dashboard.api_distribucion_costos, name='api_distribucion_costos'),
    path('api/dashboard/margen-por-producto/', views_dashboard.api_margen_por_producto, name='api_margen_por_producto'),
    path('api/dashboard/productos-rentables/', views_dashboard.api_productos_rentables, name='api_productos_rentables'),
    path('api/dashboard/totales-globales/', views_dashboard.api_totales_globales, name='api_totales_globales'),
    # Add the missing URL for semanas-disponibles
    path('api/dashboard/semanas-disponibles/', views_dashboard.api_semanas_disponibles, name='api_semanas_disponibles'),
    path('enviar_factura_email/<int:venta_id>/', views_enviar_correos.enviar_factura_email, name='enviar_factura_email'),
    path('enviar_albaran_email/<int:venta_id>/', views_enviar_correos.enviar_albaran_email, name='enviar_albaran_email'),
    path('enviar_rectificativa_email/<int:venta_id>/', views_enviar_correos.enviar_rectificativa_email, name='enviar_rectificativa_email'),
    
    # URLs para el envío de albaranes a agencias de aduana
    path('get_agencias_aduana/', views_enviar_correos.get_agencias_aduana, name='get_agencias_aduana'),
    path('get_ventas_recientes/', views_enviar_correos.get_ventas_recientes, name='get_ventas_recientes'),
    path('get_awbs_recientes/', views_enviar_correos.get_awbs_recientes, name='get_awbs_recientes'),
    path('enviar_albaranes_aduana/', views_enviar_correos.enviar_albaranes_aduana, name='enviar_albaranes_aduana'),

    # URLs para descarga directa de facturas/rectificativas    path('generar-factura/<int:venta_id>/', views_ventas.generar_factura_download, name='generar-factura'),    path('generar-rectificativa/<int:venta_id>/', views_ventas.generar_rectificativa_download, name='generar-rectificativa'),    # Nueva URLs para acceso por token a facturas y rectificativas
    path('cliente-factura/<int:venta_id>/<str:token>/', views_ventas.factura_cliente_token, name='factura_cliente_token'),
    path('cliente-rectificativa/<int:venta_id>/<str:token>/', views_ventas.rectificativa_cliente_token, name='rectificativa_cliente_token'),
]
