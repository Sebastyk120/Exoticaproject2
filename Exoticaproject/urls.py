from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from autenticacion.views import login_view, logout_view, home_view, index_view, landing_page_view

urlpatterns = [
    # Root URL now points to the public landing page
    path('', landing_page_view, name='landing_page'),
    
    # Internal application routes
    path('app/', index_view, name='index'),
    path('app/login/', login_view, name='login'),
    path('app/logout/', logout_view, name='logout'),
    path('app/home/', home_view, name='home'),
    
    # Admin and other app URLs
    path('admin/', admin.site.urls),
    path('autenticacion/', include('autenticacion.urls')),
    path('importacion/', include('importacion.urls')),
    path('productos/', include('productos.urls')),
    path('comercial/', include('comercial.urls', namespace='comercial')),

] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Personaliza el título del admin
admin.site.site_header = 'Administración L&M Exótica'
admin.site.site_title = 'Administración L&M Exótica'
admin.site.index_title = 'Panel de Control'