from django.urls import path
from . import views
from . import views_aduana

app_name = 'importacion'

urlpatterns = [
    # Rutas principales de importación (si las necesitas)
    # path('', views.index, name='index'),
    
    # Ruta para cargar y procesar PDF de aduana
    path('aduana-pdf/', views_aduana.process_pdf, name='aduana_pdf'),
]