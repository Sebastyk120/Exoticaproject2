from django.apps import AppConfig
import os
from django.conf import settings

def ensure_media_directories():
    """
    Asegura que todos los subdirectorios necesarios para archivos de medios existan.
    Debe llamarse durante la inicialización de la aplicación.
    """
    directories = [
        'frutas',  # Para las imágenes de frutas
        # Añada más directorios según sea necesario
    ]
    
    for directory in directories:
        directory_path = os.path.join(settings.MEDIA_ROOT, directory)
        if not os.path.exists(directory_path):
            os.makedirs(directory_path, exist_ok=True)
            print(f"Directorio creado: {directory_path}")

class ProductosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'productos'

    def ready(self):
        ensure_media_directories()
