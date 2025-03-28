from django.urls import path
from . import views
from . import views_aduana
from . import views_carga
from . import views_pedidos
from . import views_transferencias

app_name = 'importacion'

urlpatterns = [
    # Existing URLs for aduana and carga
    path('aduana-pdf/', views_aduana.process_pdf, name='aduana_pdf'),
    path('carga-pdf/', views_carga.process_pdf, name='carga_pdf'),
    
    # Bodega URL
    path('bodega/', views.bodega_view, name='bodega'),
    
    # Gastos Aduana CRUD URLs
    path('aduana/gasto/<int:gasto_id>/', views_aduana.get_gasto, name='get_gasto'),
    path('aduana/gasto/<int:gasto_id>/update/', views_aduana.update_gasto, name='update_gasto'),
    path('aduana/gasto/<int:gasto_id>/delete/', views_aduana.delete_gasto, name='delete_gasto'),
    
    # Gastos Carga CRUD URLs
    path('carga/gasto/<int:gasto_id>/', views_carga.get_gasto, name='get_gasto_carga'),
    path('carga/gasto/<int:gasto_id>/update/', views_carga.update_gasto, name='update_gasto_carga'),
    path('carga/gasto/<int:gasto_id>/delete/', views_carga.delete_gasto, name='delete_gasto_carga'),
    
    # URLs for orders
    path('pedidos/', views_pedidos.lista_pedidos, name='lista_pedidos'),
    path('pedidos/nuevo/', views_pedidos.nuevo_pedido, name='nuevo_pedido'),
    path('pedidos/<int:pedido_id>/', views_pedidos.detalle_pedido, name='detalle_pedido'),
    path('pedidos/guardar/', views_pedidos.guardar_pedido, name='guardar_pedido'),
    path('pedidos/<int:pedido_id>/guardar/', views_pedidos.guardar_pedido, name='guardar_pedido'),
    path('pedidos/<int:pedido_id>/detalle/guardar/', views_pedidos.guardar_detalle, name='guardar_detalle'),
    path('pedidos/<int:pedido_id>/detalle/<int:detalle_id>/guardar/', views_pedidos.guardar_detalle, name='guardar_detalle'),
    path('pedidos/<int:pedido_id>/guardar-detalles-batch/', views_pedidos.guardar_detalles_batch, name='guardar_detalles_batch'),
    path('pedidos/<int:pedido_id>/detalles-json/', views_pedidos.obtener_detalles_pedido, name='obtener_detalles_pedido'),
    path('pedidos/<int:pedido_id>/solicitar/', views_pedidos.solicitar_pedido, name='solicitar_pedido'),
    path('obtener-precio-presentacion/<int:presentacion_id>/<int:exportador_id>/', views_pedidos.obtener_precio_presentacion, name='obtener_precio_presentacion'),

    # URLs for transferencias
    path('transferencias/', views_transferencias.transferencias_view, name='transferencias'),
    # Exportador CRUD
    path('transferencias/exportador/crear/', views_transferencias.crear_transferencia_exportador, name='crear_transferencia_exportador'),
    path('transferencias/exportador/<int:pk>/editar/', views_transferencias.editar_transferencia_exportador, name='editar_transferencia_exportador'),
    path('transferencias/exportador/<int:pk>/eliminar/', views_transferencias.eliminar_transferencia_exportador, name='eliminar_transferencia_exportador'),
    
    # Aduana CRUD
    path('transferencias/aduana/crear/', views_transferencias.crear_transferencia_aduana, name='crear_transferencia_aduana'),
    path('transferencias/aduana/<int:pk>/editar/', views_transferencias.editar_transferencia_aduana, name='editar_transferencia_aduana'),
    path('transferencias/aduana/<int:pk>/eliminar/', views_transferencias.eliminar_transferencia_aduana, name='eliminar_transferencia_aduana'),
    
    # Carga CRUD
    path('transferencias/carga/crear/', views_transferencias.crear_transferencia_carga, name='crear_transferencia_carga'),
    path('transferencias/carga/<int:pk>/editar/', views_transferencias.editar_transferencia_carga, name='editar_transferencia_carga'),
    path('transferencias/carga/<int:pk>/eliminar/', views_transferencias.eliminar_transferencia_carga, name='eliminar_transferencia_carga'),
]