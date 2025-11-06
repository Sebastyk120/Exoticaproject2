import io
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.apps import apps
from django.core.management import call_command
from django.contrib.auth.decorators import login_required
from django.urls import get_resolver, reverse, NoReverseMatch
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from comercial.models import Cliente, Venta, EmailLog, Cotizacion
from productos.models import Fruta, Presentacion
from importacion.models import Pedido
import importlib
import inspect
from .forms import ContactForm  # Importar el nuevo formulario

def index_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    return redirect('login')

def login_view(request):
    # Si el usuario ya está autenticado, redirigir a home
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                # Redirect to home page after successful login
                return redirect('home')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    # Redirect to the app login page after logout, not the public landing page
    return redirect('login')  # Redirect to login page after logout

@login_required
def home_view(request):
    """View for the home page with dynamic menu."""
    # Get counts for dashboard statistics
    client_count = Cliente.objects.count()
    product_count = Presentacion.objects.count()
    import_count = Pedido.objects.count()
    sales_count = Venta.objects.count()
    email_count = EmailLog.objects.count()
    cotizacion_count = Cotizacion.objects.count()
    
    # Get all clients for the modal
    clientes = Cliente.objects.all().order_by('nombre')
    
    context = {
        'user': request.user,
        'client_count': client_count,
        'product_count': product_count,
        'import_count': import_count,
        'sales_count': sales_count,
        'email_count': email_count,
        'cotizacion_count': cotizacion_count,
        'clientes': clientes,
    }
    
    return render(request, 'home.html', context)

class CustomPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    success_url = '/autenticacion/password_reset/done/'
    title = 'Restablecer Contraseña - L&M Exotic Fruit'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_name'] = "L&M Exotic Fruit"
        context['site_header'] = "L&M Exotic Fruit"
        return context

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'registration/password_reset_done.html'
    title = 'Correo Enviado - L&M Exotic Fruit'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'registration/password_reset_confirm.html'
    success_url = '/autenticacion/password_reset/complete/'
    title = 'Nueva Contraseña - L&M Exotic Fruit'

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'registration/password_reset_complete.html'
    title = 'Contraseña Restablecida - L&M Exotic Fruit'

def landing_page_view(request):
    """Vista para la página de inicio pública con optimización SEO."""
    # Obtener todas las frutas ordenadas por nombre
    fruits = Fruta.objects.all().order_by('nombre')
    
    # Determinar qué sección mostrar según el hash en la URL si existe
    section = request.GET.get('section', '')
    
    # Contexto SEO personalizado según la sección
    seo_context = {
        'meta_title': 'L&M Exotic Fruits - Importador Mayorista de Frutas Exóticas Premium en España',
        'meta_description': 'Importadores y distribuidores mayoristas de frutas exóticas premium desde 2017. Mangostino, pitahaya, gulupa y más con la mejor calidad y servicio en toda España y Europa.',
        'canonical_url': f"{settings.BASE_URL}{reverse('landing_page')}",
        'og_type': 'website',
    }
    
    # Actualizar contexto SEO según la sección
    if section == 'about':
        seo_context.update({
            'meta_title': 'Sobre Nosotros | L&M Exotic Fruits - Importadores de Frutas Exóticas',
            'meta_description': 'Desde 2017 en L&M Exotic Fruits importamos y distribuimos frutas exóticas premium para toda España y Europa. Conoce nuestra historia y compromiso con la calidad.',
            'canonical_url': f"{settings.BASE_URL}{reverse('landing_page_about')}",
        })
    elif section == 'products':
        seo_context.update({
            'meta_title': 'Nuestros Productos | L&M Exotic Fruits - Frutas Tropicales Premium',
            'meta_description': 'Descubre nuestra selección de frutas exóticas premium: mangostino, pitahaya, gulupa, granadilla, uchuva y más. Calidad excepcional para el mercado español.',
            'canonical_url': f"{settings.BASE_URL}{reverse('landing_page_products')}",
        })
    elif section == 'contact':
        seo_context.update({
            'meta_title': 'Contacto | L&M Exotic Fruits - Mayorista Frutas Exóticas',
            'meta_description': 'Contacta con L&M Exotic Fruits para pedidos mayoristas de frutas exóticas premium. Servicio para toda España y Europa con la mejor calidad garantizada.',
            'canonical_url': f"{settings.BASE_URL}{reverse('landing_page_contact')}",
        })
    
    # Preparar el formulario de contacto
    form = ContactForm()
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # Procesar el formulario y enviar el correo
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            
            # Enviar el email
            subject_email = f'Nuevo contacto desde la web: {subject}'
            message_email = f'Nombre: {name}\nEmail: {email}\n\nMensaje:\n{message}'
            
            send_mail(
                subject_email,
                message_email,
                settings.DEFAULT_FROM_EMAIL,
                [settings.CONTACT_EMAIL],
                fail_silently=False,
            )
            
            # Devolver a la misma página con mensaje de éxito
            messages.success(request, 'Tu mensaje ha sido enviado correctamente. Nos pondremos en contacto contigo pronto.')
            return redirect('landing_page')
    # Contexto para la plantilla
    context = {
        'frutas': fruits,
        'form': form,
        'section': section,
        **seo_context,
    }
    
    # Renderizar la plantilla
    return render(request, 'index.html', context)


