from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from datetime import datetime
from django.conf import settings

class StaticViewSitemap(Sitemap):
    priority = 1.0
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        # Incluye todas las secciones de la página principal y otras páginas importantes
        return ['landing_page', 'landing_page_about', 'landing_page_products', 'landing_page_contact', 'login']

    def location(self, item):
        if item == 'landing_page':
            return reverse(item)
        elif item == 'login':
            return reverse(item)
        else:
            # Para las secciones específicas de la página principal, añadir el hash correspondiente
            section = item.replace('landing_page_', '')
            return f"{reverse('landing_page')}#{section}"
    
    def lastmod(self, item):
        # Devuelve la fecha de la última modificación
        return datetime.now()

# Sitemap para los productos (aunque sea una SPA, Google los indexará mejor si tienen URLs individuales)
class ProductsSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        # Importando aquí para evitar importaciones circulares
        from productos.models import Fruta
        return Fruta.objects.all()

    def location(self, item):
        # Retorna la URL al producto específico en la sección de productos
        return f"{reverse('landing_page')}#product-{item.id}"
    
    def lastmod(self, item):
        # Usar la fecha de última actualización del producto si está disponible
        # o la fecha actual si no lo está
        return getattr(item, 'fecha_actualizacion', datetime.now())
    
    # Agregar imágenes al sitemap de productos
    def _urls(self, page, site, protocol):
        urls = []
        latest_lastmod = None
        
        # Obtener todos los items
        all_items = self.items()
        
        # Paginar resultados si es necesario
        if self.limit is not None:
            i_start = self.limit * (page - 1)
            i_end = self.limit * page
            all_items = all_items[i_start:i_end]
        
        for item in all_items:
            loc = f"{protocol}://{site.domain}{self.location(item)}"
            lastmod = self.lastmod(item) if self.lastmod is not None else None
            
            # Actualizar latest_lastmod si es necesario
            if lastmod is not None and (latest_lastmod is None or lastmod > latest_lastmod):
                latest_lastmod = lastmod
            
            # Agregar objeto URL con información de imágenes
            url_info = {
                'item': item,
                'location': loc,
                'lastmod': lastmod,
                'changefreq': self.changefreq,
                'priority': self.priority,
                'images': self._get_image_info(item),  # Obtener información de las imágenes
            }
            
            urls.append(url_info)
        
        return urls
    
    def _get_image_info(self, item):
        """Obtener información de las imágenes para el sitemap."""
        images = []
        
        # Verificar si el ítem tiene una imagen
        if item.imagen and item.imagen.url:
            # Construir URL completa para la imagen
            if item.imagen.url.startswith('http'):
                image_url = item.imagen.url
            else:
                image_url = f"{settings.BASE_URL}{item.imagen.url}"
            
            images.append({
                'src': image_url,
                'title': f"{item.nombre} - L&M Exotic Fruits",
            })
        
        return images

# Sitemap para las secciones de blog o noticias que puedan existir
class NewsSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.9
    protocol = 'https'
    
    def items(self):
        # Si tienes un modelo de Blog o Noticias, úsalo aquí
        # Por ahora, devolvemos una lista vacía
        return []
    
    def location(self, item):
        # Para futura implementación
        return reverse('landing_page') + f"#news-{item.id}"
