from django.urls import path
from . import views_clientes, views_ventas

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
    path('validar-stock/<int:presentacion_id>/<int:cajas_enviadas>/', views_ventas.validar_stock, name='validar_stock'),
]
