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
    path('bodega/json/', views.bodega_json, name='bodega_json'),
    
    # Gastos Aduana CRUD URLs
    path('aduana/gasto/<int:gasto_id>/', views_aduana.get_gasto, name='get_gasto'),
    path('aduana/gasto/<int:gasto_id>/update/', views_aduana.update_gasto, name='update_gasto'),
    path('aduana/gasto/<int:gasto_id>/delete/', views_aduana.delete_gasto, name='delete_gasto'),
    path('aduana/gasto/create/', views_aduana.create_gasto, name='create_gasto_aduana'),
    
    # Gastos Carga CRUD URLs
    path('carga/gasto/<int:gasto_id>/', views_carga.get_gasto, name='get_gasto_carga'),
    path('carga/gasto/<int:gasto_id>/update/', views_carga.update_gasto, name='update_gasto_carga'),
    path('carga/gasto/<int:gasto_id>/delete/', views_carga.delete_gasto, name='delete_gasto_carga'),
    path('carga/gasto/create/', views_carga.create_gasto, name='create_gasto'),
    
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
    path('enviar_pedido_email/<int:pedido_id>/', views.enviar_pedido_email, name='enviar_pedido_email'),
    
    # Add the API endpoint that matches what the JavaScript is calling
    path('api/precio/<int:presentacion_id>/<int:exportador_id>/', views_pedidos.obtener_precio_presentacion, name='api_precio_presentacion'),

        # URLs for transferencias

        path('transferencias/', views_transferencias.transferencias_view, name='transferencias'),

        path('transferencias/exportador/', views_transferencias.TransferenciasExportadorListView.as_view(), name='transferencias_exportador_list'),

        path('transferencias/aduana/', views_transferencias.TransferenciasAduanaListView.as_view(), name='transferencias_aduana_list'),

        path('transferencias/carga/', views_transferencias.TransferenciasCargaListView.as_view(), name='transferencias_carga_list'),

        path('transferencias/cliente/', views_transferencias.TransferenciasClienteListView.as_view(), name='transferencias_cliente_list'),

    

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

    

        # Cliente CRUD

        path('transferencias/cliente/crear/', views_transferencias.crear_transferencia_cliente, name='crear_transferencia_cliente'),

        path('transferencias/cliente/<int:pk>/editar/', views_transferencias.editar_transferencia_cliente, name='editar_transferencia_cliente'),

        path('transferencias/cliente/<int:pk>/eliminar/', views_transferencias.eliminar_transferencia_cliente, name='eliminar_transferencia_cliente'),

    

        # New path for balance data API

        path('transferencias/get-balances-data/', views_transferencias.get_balances_data, name='get_balances_data'),
]