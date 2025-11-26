import io
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
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
from django.http import JsonResponse
from comercial.models import Cliente, Venta, EmailLog, Cotizacion
from productos.models import Fruta, Presentacion
from importacion.models import Pedido
from comercial.views_enviar_correos import send_email_with_mailjet
import importlib
import inspect
import traceback
from decimal import Decimal
from .forms import ContactForm  # Importar el nuevo formulario

logger = logging.getLogger(__name__)

def format_currency_eur(value):
    """Format a value as Euro currency."""
    try:
        formatted_value = '{:,.2f}'.format(float(value)).replace(',', '@').replace('.', ',').replace('@', '.')
        return f"{formatted_value} €"
    except (ValueError, TypeError):
        return value

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

@login_required
def enviar_estado_cuenta_email(request):
    """
    Vista para enviar el resumen del estado de cuenta de un cliente por correo electrónico.
    Incluye las facturas próximas a vencer y pendientes de pago como contenido del mensaje.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Se requiere método POST'
        }, status=400)

    try:
        # Obtener datos del request
        cliente_id = request.POST.get('cliente_id')
        selected_emails_json = request.POST.get('selected_emails')
        custom_subject = request.POST.get('email_subject')
        custom_message = request.POST.get('email_message')
        
        if not cliente_id:
            return JsonResponse({
                'success': False,
                'error': 'No se especificó el cliente'
            })

        # Obtener el cliente
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        
        # Procesar correos seleccionados
        if selected_emails_json:
            try:
                emails = json.loads(selected_emails_json)
                if not isinstance(emails, list):
                    emails = []
            except json.JSONDecodeError:
                emails = []
        else:
            # Usar correos por defecto del cliente
            emails = [cliente.email] if cliente.email else []
            if cliente.correos_adicionales:
                additional_emails = [email.strip() for email in cliente.correos_adicionales.split(',') if email.strip()]
                emails.extend(additional_emails)

        if not emails:
            return JsonResponse({
                'success': False,
                'error': 'No se seleccionaron direcciones de correo electrónico'
            })

        # Obtener datos del estado de cuenta (similar a la función get_client_summary_data)
        from django.db.models import Sum, Q, F, Value, CharField, DecimalField, ExpressionWrapper
        from django.db.models.functions import Coalesce
        from datetime import datetime, timedelta
        
        # Obtener facturas del cliente
        zero_decimal = Value(Decimal('0.00'), output_field=DecimalField(max_digits=10, decimal_places=2))
        abono_expr = Coalesce(F('valor_total_abono_euro'), zero_decimal)
        facturas = Venta.objects.filter(
            cliente=cliente
        ).annotate(
            valor_abono=abono_expr,
            valor_neto=ExpressionWrapper(
                F('valor_total_factura_euro') - abono_expr,
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).order_by('-fecha_entrega')

        # Calcular estadísticas
        total_facturado = facturas.aggregate(total=Sum('valor_total_factura_euro'))['total'] or Decimal('0.00')
        total_abonos = facturas.aggregate(total=Sum('valor_total_abono_euro'))['total'] or Decimal('0.00')
        total_pagado = facturas.filter(pagado=True).aggregate(total=Sum('valor_neto'))['total'] or Decimal('0.00')
        saldo_actual = total_facturado - total_abonos - total_pagado

        # Facturas pendientes
        facturas_pendientes = facturas.filter(pagado=False)

        # Clasificar facturas por estado
        hoy = datetime.now().date()
        facturas_clasificadas = []
        
        for factura in facturas_pendientes:
            if factura.fecha_vencimiento:
                dias_hasta_vencimiento = (factura.fecha_vencimiento - hoy).days
                
                if dias_hasta_vencimiento < 0:
                    estado = 'vencida'
                    estado_display = 'Vencida'
                elif dias_hasta_vencimiento <= 7:
                    estado = 'proxima'
                    estado_display = f'Próxima ({dias_hasta_vencimiento} días)'
                else:
                    estado = 'normal'
                    estado_display = 'Normal'
            else:
                estado = 'normal'
                estado_display = 'Sin fecha'
                dias_hasta_vencimiento = None

            facturas_clasificadas.append({
                'fecha_entrega': factura.fecha_entrega.strftime('%d/%m/%Y'),
                'numero_factura': factura.numero_factura or 'N/A',
                'valor_total': factura.valor_total_factura_euro,
                'valor_abono': factura.valor_abono,
                'valor_neto': factura.valor_neto,
                'fecha_vencimiento': factura.fecha_vencimiento.strftime('%d/%m/%Y') if factura.fecha_vencimiento else '-',
                'estado': estado,
                'estado_display': estado_display,
                'dias_hasta_vencimiento': dias_hasta_vencimiento
            })

        # Ordenar facturas: vencidas primero, luego próximas, luego normales
        facturas_clasificadas.sort(key=lambda x: (
            0 if x['estado'] == 'vencida' else
            1 if x['estado'] == 'proxima' else
            2,
            x['fecha_entrega']
        ))

        subject = custom_subject or f"Estado de Cuenta - {cliente.nombre} - L&M Exotic Fruit"

        body_text = ""
        body_text += f"Estimado/a {cliente.nombre},\n\n"
        if custom_message:
            body_text += f"{custom_message}\n\n"
        hay_vencidas = any(f.get('estado') == 'vencida' for f in facturas_clasificadas)
        if hay_vencidas:
            body_text += (
                "Le recordamos que tiene facturas vencidas pendientes de pago. "
                "Agradecemos su pronta regularización.\n\n"
            )
        body_text += "Facturas pendientes de pago:\n"
        if facturas_clasificadas:
            for factura in facturas_clasificadas:
                linea = (
                    f"Factura {factura['numero_factura']} | Emisión {factura['fecha_entrega']} | "
                    f"Vencimiento {factura['fecha_vencimiento']} | Total {format_currency_eur(factura['valor_total'])} | "
                    f"Abonos {format_currency_eur(factura['valor_abono'])} | Pendiente {format_currency_eur(factura['valor_neto'])} | "
                    f"Estado {factura['estado_display']}"
                )
                body_text += linea + "\n"
        else:
            body_text += "No hay facturas pendientes de pago.\n"

        cuenta_html = ""
        if cliente.token_acceso:
            account_url = request.build_absolute_uri(f'/comercial/client-statement/{cliente.token_acceso}/')
            cuenta_html = (
                f"<div style=\"margin-top:16px;\"><strong>Consulte su estado de cuenta en línea:</strong><br>"
                f"<a href=\"{account_url}\" target=\"_blank\">{account_url}</a></div>"
            )

        tabla_estilos = (
            "width:100%;border-collapse:collapse;font-family:Arial,Helvetica,sans-serif;font-size:14px;"
        )
        th_estilos = (
            "background:#f2f4f7;color:#333;text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;"
        )
        td_estilos = "padding:8px;border-bottom:1px solid #e5e7eb;"

        def fila_bg(estado):
            if estado == 'vencida':
                return "background-color:#f8d7da;"
            if estado == 'proxima':
                return "background-color:#fff3cd;"
            if estado == 'normal':
                return "background-color:#d4edda;"
            return ""

        def badge_html(estado, texto):
            if estado == 'vencida':
                color = "#721c24"
                bg = "#f8d7da"
            elif estado == 'proxima':
                color = "#856404"
                bg = "#fff3cd"
            else:
                color = "#155724"
                bg = "#d4edda"
            return f"<span style=\"display:inline-block;padding:4px 8px;border-radius:6px;font-weight:600;color:{color};background:{bg};\">{texto}</span>"

        filas_html = ""
        if facturas_clasificadas:
            for f in facturas_clasificadas:
                estado_text = f['estado_display']
                if f['estado'] == 'vencida' and f.get('dias_hasta_vencimiento') is not None:
                    dias_vencidos = abs(f['dias_hasta_vencimiento'])
                    estado_text = f"Vencida ({dias_vencidos} días)"
                filas_html += (
                    f"<tr style=\"{fila_bg(f['estado'])}\">"
                    f"<td style=\"{td_estilos}\">{f['fecha_entrega']}</td>"
                    f"<td style=\"{td_estilos}\">{f['numero_factura']}</td>"
                    f"<td style=\"{td_estilos}\">{format_currency_eur(f['valor_total'])}</td>"
                    f"<td style=\"{td_estilos}\">{format_currency_eur(f['valor_abono'])}</td>"
                    f"<td style=\"{td_estilos}\"><strong>{format_currency_eur(f['valor_neto'])}</strong></td>"
                    f"<td style=\"{td_estilos}\">{f['fecha_vencimiento']}</td>"
                    f"<td style=\"{td_estilos}\">{badge_html(f['estado'], estado_text)}</td>"
                    f"</tr>"
                )
        else:
            filas_html = (
                f"<tr><td colspan=\"7\" style=\"{td_estilos}\">"
                f"<span style=\"color:#28a745;font-weight:600;\">No hay facturas pendientes de pago</span>"
                f"</td></tr>"
            )

        body_html = (
            f"<div style=\"font-family:Arial,Helvetica,sans-serif;color:#333;\">"
            f"<p>Estimado/a {cliente.nombre},</p>"
            f"{('<p>Le recordamos que tiene las siguientes facturas vencidas pendientes de pago. Agradecemos su pronta regularización.</p>') if hay_vencidas else ''}"
            f"{f'<p>{custom_message}</p>' if custom_message else ''}"
            f"<h3 style=\"margin:16px 0;\">Facturas Próximas a Vencer / Pendientes de Pago</h3>"
            f"<table style=\"{tabla_estilos}\">"
            f"<thead><tr>"
            f"<th style=\"{th_estilos}\">F. Emisión</th>"
            f"<th style=\"{th_estilos}\">Nº Factura</th>"
            f"<th style=\"{th_estilos}\">Total Factura</th>"
            f"<th style=\"{th_estilos}\">Abonos</th>"
            f"<th style=\"{th_estilos}\">Pendiente</th>"
            f"<th style=\"{th_estilos}\">F. Vencimiento</th>"
            f"<th style=\"{th_estilos}\">Estado</th>"
            f"</tr></thead>"
            f"<tbody>{filas_html}</tbody>"
            f"</table>"
            f"{cuenta_html}"
            f"<div style=\"margin-top:24px;\">"
            f"<p>Atentamente,<br>Luz Mery Melo Mejia<br>L&M Exotic Fruit</p>"
            f"<p style=\"font-size:12px;color:#666;\">Este es un mensaje automático del sistema de gestión de L&M Exotic Fruit.</p>"
            f"</div>"
            f"</div>"
        )

        # Enviar email usando Mailjet
        success, error, email_log = send_email_with_mailjet(
            subject=subject,
            body=body_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=emails,
            proceso='estado_cuenta',
            usuario=request.user,
            cliente=cliente,
            body_html=body_html
        )
        
        if not success:
            raise Exception(f"Error enviando email: {error}")

        return JsonResponse({
            'success': True,
            'emails': ", ".join(emails),
            'cliente': cliente.nombre
        })

    except Exception as e:
        import traceback
        logger.error(f"Error al enviar estado de cuenta: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


