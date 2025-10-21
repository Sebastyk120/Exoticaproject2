from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from .models import Bodega, Pedido
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from comercial.views_enviar_correos import send_email_with_mailjet
import base64
from datetime import datetime

# Create your views here.

@login_required
def bodega_view(request):
    """
    View to display the warehouse inventory.
    """
    bodegas = Bodega.objects.select_related('presentacion', 'presentacion__fruta').all()
    context = {
        'bodegas': bodegas,
    }
    return render(request, 'bodega/bodega.html', context)

@login_required
def bodega_json(request):
    """
    API endpoint to get warehouse inventory data in JSON format.
    """
    bodegas = Bodega.objects.select_related('presentacion', 'presentacion__fruta').all()
    
    bodegas_data = []
    for bodega in bodegas:
        bodega_data = {
            'id': bodega.id,
            'stock_actual': bodega.stock_actual,
            'ultima_actualizacion': bodega.ultima_actualizacion.strftime('%d/%m/%Y %H:%M') if bodega.ultima_actualizacion else None,
            'presentacion': {
                'id': bodega.presentacion.id,
                'nombre': str(bodega.presentacion),
                'kilos': bodega.presentacion.kilos,
                'fruta': str(bodega.presentacion.fruta) if bodega.presentacion.fruta else None
            }
        }
        bodegas_data.append(bodega_data)
    
    return JsonResponse({
        'bodegas': bodegas_data
    })

@login_required
def eliminar_pedido(request, pedido_id):
    """Elimina un pedido si no tiene productos vendidos"""
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    
    try:
        with transaction.atomic():
            pedido.delete()
        messages.success(request, f'Pedido #{pedido_id} eliminado correctamente.')
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Error al eliminar el pedido: {str(e)}')
    
    return redirect('importacion:lista_pedidos')

@login_required
def enviar_pedido_email(request, pedido_id):
    """
    Vista para enviar el PDF de solicitud de pedido generado en el cliente por correo electrónico
    al exportador y los correos adicionales registrados.
    Actualizado para usar la configuración optimizada de Mailjet.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Se requiere método POST'
        }, status=400)

    # Obtener el PDF codificado en base64 desde la solicitud
    pdf_data = request.POST.get('pdf_data')
    if not pdf_data:
        return JsonResponse({
            'success': False,
            'error': 'No se recibieron datos PDF'
        }, status=400)

    try:
        # Si viene como data URI, extraer solo la parte base64
        if 'base64,' in pdf_data:
            pdf_base64 = pdf_data.split('base64,')[1]
        else:
            pdf_base64 = pdf_data
        
        # Decodificar los datos PDF
        pdf_bytes = base64.b64decode(pdf_base64)
        
        # Obtener la información del pedido
        pedido = get_object_or_404(Pedido, pk=pedido_id)
        
        # Obtener los correos seleccionados por el usuario (si se envían)
        selected_emails_json = request.POST.get('selected_emails')
        if selected_emails_json:
            try:
                import json
                emails = json.loads(selected_emails_json)
                # Asegurar que emails es una lista
                if not isinstance(emails, list):
                    emails = []
            except json.JSONDecodeError:
                emails = []
        else:
            # Si no se especificaron correos seleccionados, usar todos los correos del exportador
            emails = [pedido.exportador.email] if pedido.exportador.email else []
            if pedido.exportador.correos_adicionales:
                # Añadir correos adicionales si existen (separados por coma)
                additional_emails = [email.strip() for email in pedido.exportador.correos_adicionales.split(',') if email.strip()]
                emails.extend(additional_emails)
        
        if not emails:
            return JsonResponse({
                'success': False,
                'error': 'No se seleccionaron direcciones de correo electrónico'
            })
        
        # Obtener asunto y mensaje personalizados (si se envían)
        custom_subject = request.POST.get('email_subject')
        custom_message = request.POST.get('email_message')
        
        # Preparar el mensaje de correo
        subject = custom_subject or f"Solicitud de Pedido #{pedido.id} - L&M Exotic Fruit"
        body = f"""
Estimado/a {pedido.exportador.nombre},

Adjunto encontrará la solicitud del pedido #{pedido.id}.

Fecha de emisión: {datetime.now().strftime('%d/%m/%Y')}
Fecha de entrega solicitada: {pedido.fecha_entrega.strftime('%d/%m/%Y')}
Semana: {pedido.semana}
"""

        # Añadir mensaje personalizado si existe
        if custom_message:
            body += f"""
{custom_message}
"""

        body += """
Por favor, preparar el envío para la fecha indicada y asegurar que el producto cumpla con todas las normativas de exportación.
Para cualquier aclaración, no dude en contactarnos.

Gracias por su colaboración.

Atentamente,
Luz Mery Melo Mejia
L&M Exotic Fruit
        """
        
        # Preparar adjunto para Mailjet
        filename = f'Solicitud_Pedido_{pedido.id}_{pedido.exportador.nombre.replace(" ", "_")}.pdf'
        attachments = [(filename, pdf_bytes, 'application/pdf')]
        
        # Enviar email usando Mailjet directamente para mejor manejo de adjuntos
        success, error, email_log = send_email_with_mailjet(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=emails,
            attachments=attachments,
            proceso='pedido',
            usuario=request.user,
            venta=None,
            cotizacion=None,
            cliente=None
        )
        
        if not success:
            raise Exception(f"Error enviando email: {error}")
        
        return JsonResponse({
            'success': True,
            'emails': ", ".join(emails)
        })
    
    except Exception as e:
        import traceback
        print(f"Error al procesar el PDF: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


