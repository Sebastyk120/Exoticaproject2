from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from autenticacion.views import login_view, logout_view, home_view

urlpatterns = [
    # Redirect root URL to login page
    path('', RedirectView.as_view(url='login/', permanent=False), name='index'),
    
    # Authentication routes
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('home/', home_view, name='home'),
    
    # Admin and other app URLs
    path('admin/', admin.site.urls),
    path('autenticacion/', include('autenticacion.urls')),
    path('importacion/', include('importacion.urls')),
    path('productos/', include('productos.urls')),

] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Personaliza el título del admin
admin.site.site_header = 'Administración L&M Exótica'
admin.site.site_title = 'Administración L&M Exótica'
admin.site.index_title = 'Panel de Control'