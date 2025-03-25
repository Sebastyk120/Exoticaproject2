from django.apps import AppConfig

class ImportacionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'importacion'
    
    def ready(self):
        import importacion.signals  # Register signals when the app is ready
