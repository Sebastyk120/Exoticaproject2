from django.urls import path
from . import views

urlpatterns = [
    path('frutas/', views.frutas_view, name='frutas_view'),
    path('frutas/create/', views.create_fruta, name='create_fruta'),
    
    # Rutas para presentaciones (solo visualización y creación)
    path('presentaciones/', views.presentaciones_view, name='presentaciones_view'),
    path('presentaciones/create/', views.create_presentacion, name='create_presentacion'),
    
    # Rutas para la lista de precios de importación
    path('precios-importacion/', views.lista_precios_importacion, name='lista_precios_importacion'),
    path('precios-importacion/crear/', views.crear_precio_importacion, name='crear_precio_importacion'),
    path('precios-importacion/editar/<int:precio_id>/', views.editar_precio_importacion, name='editar_precio_importacion'),
    
    # Rutas para la lista de precios de ventas
    path('precios-ventas/', views.lista_precios_ventas, name='lista_precios_ventas'),
    path('precios-ventas/crear/', views.crear_precio_ventas, name='crear_precio_ventas'),
    path('precios-ventas/editar/<int:precio_id>/', views.editar_precio_ventas, name='editar_precio_ventas'),
    
    # Rutas para cotizaciones
    path('cotizaciones/', views.lista_cotizaciones, name='lista_cotizaciones'),
    path('cotizaciones/cliente/<int:cliente_id>/', views.cotizacion_cliente, name='cotizacion_cliente'),
    path('cotizaciones/nuevo-prospecto/', views.cotizacion_prospecto, name='cotizacion_prospecto'),
    path('cotizaciones/enviar/', views.enviar_cotizacion, name='enviar_cotizacion'),
    path('cotizaciones/<int:cotizacion_id>/', views.ver_cotizacion, name='ver_cotizacion'),
]
