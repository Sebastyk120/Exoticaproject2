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
from comercial.models import Cliente, Venta
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
    
    context = {
        'user': request.user,
        'client_count': client_count,
        'product_count': product_count,
        'import_count': import_count,
        'sales_count': sales_count,
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
    
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject'] or 'Consulta desde el sitio web'
            message = form.cleaned_data['message']
            
            # Preparar el contenido del email
            email_message = f"Nombre: {name}\nEmail: {email}\nAsunto: {subject}\n\nMensaje:\n{message}"
            
            # Enviar email
            try:
                send_mail(
                    f"Contacto sitio web: {subject}",
                    email_message,
                    settings.DEFAULT_FROM_EMAIL,
                    ['import@luzmeloexoticfruits.com'],
                    fail_silently=False,
                )
                messages.success(request, 'Tu mensaje ha sido enviado con éxito. Nos pondremos en contacto contigo pronto.')
            except Exception as e:
                messages.error(request, 'Ha ocurrido un error al enviar el mensaje. Por favor, inténtalo de nuevo más tarde.')
        else:
            # Si hay errores de validación (incluyendo el captcha)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
        
        # Redireccionar a la misma página con el ancla del formulario
        return redirect(f"{request.path}#contact")
    
    else:
        form = ContactForm()  # Crear formulario vacío para GET
    
    return render(request, 'index.html', {'form': form})


