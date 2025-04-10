import base64
import io
import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.core.mail import EmailMessage
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.template.defaultfilters import register
from comercial.templatetags.custom_filters import format_currency_eur
from .models import Venta
from decimal import Decimal
from importacion.models import AgenciaAduana

@login_required
def enviar_factura_email(request, venta_id):
    """
    Vista para enviar el PDF generado en el cliente por correo electrónico
    al cliente principal y los correos adicionales.
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

    # Extraer los datos base64 reales
    try:
        # Si viene como data URI, extraer solo la parte base64
        if 'base64,' in pdf_data:
            pdf_base64 = pdf_data.split('base64,')[1]
        else:
            # Asumir que ya es base64
            pdf_base64 = pdf_data
        
        # Decodificar los datos PDF
        pdf_bytes = base64.b64decode(pdf_base64)
        
        # Obtener la información de la venta
        venta = get_object_or_404(Venta, pk=venta_id)
        
        # Obtener los correos seleccionados por el usuario
        selected_emails_json = request.POST.get('selected_emails')
        if selected_emails_json:
            try:
                emails = json.loads(selected_emails_json)
                # Asegurar que emails es una lista
                if not isinstance(emails, list):
                    emails = []
            except json.JSONDecodeError:
                emails = []
        else:
            # Si no se especificaron correos seleccionados, usar el comportamiento anterior
            emails = [venta.cliente.email] if venta.cliente.email else []  # Correo principal
            if venta.cliente.correos_adicionales:
                # Añadir correos adicionales si existen (separados por coma)
                additional_emails = [email.strip() for email in venta.cliente.correos_adicionales.split(',') if email.strip()]
                emails.extend(additional_emails)
        
        if not emails:
            return JsonResponse({
                'success': False,
                'error': 'No se seleccionaron direcciones de correo electrónico'
            })
        
        # Obtener asunto y mensaje personalizados
        custom_subject = request.POST.get('email_subject')
        custom_message = request.POST.get('email_message')
        
        # Generar enlace para el estado de cuenta del cliente
        account_link = ""
        if venta.cliente.token_acceso:
            account_url = request.build_absolute_uri(f'/comercial/client-statement/{venta.cliente.token_acceso}/')
            account_link = f"\nConsulte y descargue fácilmente su estado de cuenta, facturas y facturas de abono a través del siguiente enlace: {account_url}"
        
        # Preparar el mensaje de correo
        subject = custom_subject or f"Factura #{venta.numero_factura} - L&M Exotic Fruit"
        body = f"""
Estimado/a {venta.cliente.nombre},

Adjunto encontrará la factura #{venta.numero_factura} correspondiente a su compra.

Fecha de emisión: {venta.fecha_entrega.strftime('%d/%m/%Y')}
Fecha de vencimiento: {venta.fecha_vencimiento.strftime('%d/%m/%Y')}
Importe total: {format_currency_eur(venta.valor_total_factura_euro)}{account_link}
"""

        # Añadir mensaje personalizado si existe
        if custom_message:
            body += f"""
{custom_message}
"""

        body += """
Gracias por su confianza.

Atentamente,
Luz Mery Melo Mejia
L&M Exotic Fruit
        """
        
        # Crear y enviar el email
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=emails,
        )
        
        # Adjuntar el PDF al email
        email.attach(
            f'Factura_{venta.numero_factura}_{venta.cliente.nombre.replace(" ", "_")}.pdf',
            pdf_bytes,
            'application/pdf'
        )
        
        # Enviar el email
        email.send()
        
        return JsonResponse({
            'success': True,
            'emails': ", ".join(emails)
        })
    
    except Exception as e:
        import traceback
        print(f"Error al procesar el PDF: {str(e)}")
        print(f"Tipo de datos PDF recibido: {type(pdf_data)}")
        print(f"Primeros 100 caracteres: {pdf_data[:100] if pdf_data else 'None'}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def enviar_albaran_email(request, venta_id):
    """
    Vista para enviar el PDF del albarán generado en el cliente por correo electrónico
    a los correos seleccionados por el usuario.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Se requiere método POST'
        }, status=400)

    pdf_data = request.POST.get('pdf_data')
    if not pdf_data:
        return JsonResponse({
            'success': False,
            'error': 'No se recibieron datos PDF'
        }, status=400)

    try:
        if 'base64,' in pdf_data:
            pdf_base64 = pdf_data.split('base64,')[1]
        else:
            pdf_base64 = pdf_data

        pdf_bytes = base64.b64decode(pdf_base64)
        venta = get_object_or_404(Venta, pk=venta_id)

        # Obtener los correos seleccionados por el usuario
        selected_emails_json = request.POST.get('selected_emails')
        if selected_emails_json:
            try:
                emails = json.loads(selected_emails_json)
                # Asegurar que emails es una lista
                if not isinstance(emails, list):
                    emails = []
            except json.JSONDecodeError:
                emails = []
        else:
            # Si no se especificaron correos seleccionados, usar el comportamiento anterior
            emails = [venta.cliente.email] if venta.cliente.email else []
            if venta.cliente.correos_adicionales:
                additional_emails = [email.strip() for email in venta.cliente.correos_adicionales.split(',') if email.strip()]
                emails.extend(additional_emails)

        if not emails:
            return JsonResponse({
                'success': False,
                'error': 'No se seleccionaron direcciones de correo electrónico'
            })

        # Obtener asunto y mensaje personalizados
        custom_subject = request.POST.get('email_subject')
        custom_message = request.POST.get('email_message')

        subject = custom_subject or f"Albarán Cliente #{venta.id} - L&M Exotic Fruit"
        body = f"""
Estimado/a {venta.cliente.nombre},

Adjunto encontrará el albarán correspondiente a su pedido.

Fecha de emisión: {venta.fecha_entrega.strftime('%d/%m/%Y')}
"""

        # Añadir mensaje personalizado si existe
        if custom_message:
            body += f"""
{custom_message}
"""

        body += """
Gracias por su confianza.

Atentamente,
Luz Mery Melo Mejia
L&M Exotic Fruit
        """

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=emails,
        )

        email.attach(
            f'Albaran_Cliente_{venta.id}_{venta.cliente.nombre.replace(" ", "_")}.pdf',
            pdf_bytes,
            'application/pdf'
        )

        email.send()

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

@login_required
def enviar_rectificativa_email(request, venta_id):
    """
    Vista para enviar el PDF de la factura rectificativa generado en el cliente por correo electrónico
    al cliente principal y los correos adicionales, con un mensaje específico para rectificativas.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Se requiere método POST'
        }, status=400)

    pdf_data = request.POST.get('pdf_data')
    if not pdf_data:
        return JsonResponse({
            'success': False,
            'error': 'No se recibieron datos PDF'
        }, status=400)

    try:
        if 'base64,' in pdf_data:
            pdf_base64 = pdf_data.split('base64,')[1]
        else:
            pdf_base64 = pdf_data

        pdf_bytes = base64.b64decode(pdf_base64)
        venta = get_object_or_404(Venta, pk=venta_id)
        
        # Get the IVA percentage and calculate the factor for removing IVA
        iva_percentage = venta.porcentaje_iva
        iva_factor = 1 + (iva_percentage / 100)
        
        # Calculate the same values as in generar_rectificativa view
        if not hasattr(venta, 'iva_abono'):
            venta.total_base_imponible = venta.valor_total_abono_euro / Decimal(str(iva_factor))
            venta.iva_abono = venta.total_base_imponible * (iva_percentage / 100)
        
        if not hasattr(venta, 'valor_total_abono_euro_con_iva'):
            venta.valor_total_abono_euro_con_iva = venta.valor_total_abono_euro

        # Obtener los correos seleccionados por el usuario
        selected_emails_json = request.POST.get('selected_emails')
        if selected_emails_json:
            try:
                emails = json.loads(selected_emails_json)
                # Asegurar que emails es una lista
                if not isinstance(emails, list):
                    emails = []
            except json.JSONDecodeError:
                emails = []
        else:
            # Si no se especificaron correos seleccionados, usar el comportamiento anterior
            emails = [venta.cliente.email] if venta.cliente.email else []
            if venta.cliente.correos_adicionales:
                additional_emails = [email.strip() for email in venta.cliente.correos_adicionales.split(',') if email.strip()]
                emails.extend(additional_emails)

        if not emails:
            return JsonResponse({
                'success': False,
                'error': 'No se seleccionaron direcciones de correo electrónico'
            })

        # Obtener asunto y mensaje personalizados
        custom_subject = request.POST.get('email_subject')
        custom_message = request.POST.get('email_message')

        # Generar enlace para el estado de cuenta del cliente
        account_link = ""
        if venta.cliente.token_acceso:
            account_url = request.build_absolute_uri(f'/comercial/client-statement/{venta.cliente.token_acceso}/')
            account_link = f"\nConsulte y descargue fácilmente su estado de cuenta, facturas y facturas de abono a través del siguiente enlace: {account_url}"

        # Mensaje específico para facturas rectificativas
        subject = custom_subject or f"Factura Rectificativa #{venta.numero_nc} - L&M Exotic Fruit"
        body = f"""
Estimado/a {venta.cliente.nombre},

Adjunto encontrará la factura rectificativa #{venta.numero_nc} correspondiente a la factura original #{venta.numero_factura or venta.id}.

Esta factura rectificativa abona parcial o totalmente los conceptos indicados en la factura original 
emitida con fecha {venta.fecha_entrega.strftime('%d/%m/%Y')}.

Detalles de la rectificativa:
- Número de rectificativa: {venta.numero_nc}
- Fecha de emisión: {venta.fecha_entrega.strftime('%d/%m/%Y')}
- Importe total del abono: {format_currency_eur(venta.valor_total_abono_euro_con_iva)}{account_link}
"""

        # Añadir mensaje personalizado si existe
        if custom_message:
            body += f"""
{custom_message}
"""

        body += """
Para cualquier consulta relacionada con esta rectificativa, no dude en contactarnos.

Gracias por su confianza.

Atentamente,
Luz Mery Melo Mejia
L&M Exotic Fruit
        """

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=emails,
        )

        email.attach(
            f'Factura_Rectificativa_{venta.numero_nc}_{venta.cliente.nombre.replace(" ", "_")}.pdf',
            pdf_bytes,
            'application/pdf'
        )

        email.send()

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

@login_required
def get_agencias_aduana(request):
    """
    Vista para obtener la lista de agencias de aduana disponibles
    """
    try:
        agencias = AgenciaAduana.objects.all()
        agencias_list = [
            {
                'id': a.id, 
                'nombre': a.nombre, 
                'correo': a.correo or '',
                'correos_adicionales': a.correos_adicionales or ''
            } 
            for a in agencias
        ]
        return JsonResponse(agencias_list, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_ventas_recientes(request):
    """
    Vista para obtener una lista de las ventas más recientes para seleccionar albaranes
    """
    try:
        # Obtener las últimas 50 ventas
        ventas = Venta.objects.select_related('cliente').order_by('-id')[:50]
        ventas_list = [
            {
                'id': v.id,
                'cliente': v.cliente.nombre,
                'fecha': v.fecha_entrega.strftime('%d/%m/%Y') if v.fecha_entrega else '-',
            } 
            for v in ventas
        ]
        return JsonResponse(ventas_list, safe=False)
    except Exception as e:
        import traceback
        print(f"Error al obtener ventas recientes: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_awbs_recientes(request):
    """
    Vista para obtener una lista de los AWBs más recientes de pedidos
    """
    try:
        from importacion.models import Pedido
        # Obtener los últimos 20 pedidos con AWB no vacío
        pedidos = Pedido.objects.filter(awb__isnull=False).exclude(awb='').order_by('-id')[:20]
        
        awbs_list = []
        for p in pedidos:
            try:
                # Usar getattr con valores predeterminados para evitar errores si faltan atributos
                exportador_nombre = getattr(p.exportador, 'nombre', 'Sin exportador') if p.exportador else 'Sin exportador'
                
                # Manejar con cuidado la fecha para evitar errores de formato
                fecha_str = '-'
                if hasattr(p, 'fecha_entrega') and p.fecha_entrega:
                    try:
                        fecha_str = p.fecha_entrega.strftime('%d/%m/%Y')
                    except:
                        fecha_str = 'Fecha inválida'
                
                # Construir el elemento seguro
                awbs_list.append({
                    'id': p.id,
                    'awb': p.awb or '',
                    'exportador': exportador_nombre,
                    'fecha': fecha_str,
                    'semana': p.semana or '-'
                })
            except Exception as inner_e:
                # Registrar el error pero continuar con el siguiente pedido
                print(f"Error al procesar pedido #{p.id}: {str(inner_e)}")
                continue
        
        return JsonResponse(awbs_list, safe=False)
    except Exception as e:
        import traceback
        print(f"Error al obtener AWBs recientes: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def enviar_albaranes_aduana(request):
    """
    Vista para enviar múltiples PDFs de albaranes generados en el cliente por correo electrónico
    a una agencia de aduanas seleccionada.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Se requiere método POST'
        }, status=400)

    # Verificar que se recibió la agencia y al menos un PDF
    agencia_id = request.POST.get('agencia_id')
    email_subject = request.POST.get('email_subject', 'Datos de reparto - Awb: ')
    email_message = request.POST.get('email_message', '')
    
    if not agencia_id:
        return JsonResponse({
            'success': False,
            'error': 'No se especificó la agencia de aduana'
        }, status=400)
    
    # Obtener IDs de las ventas
    try:
        venta_ids_json = request.POST.get('venta_ids')
        if venta_ids_json:
            venta_ids = json.loads(venta_ids_json)
        else:
            venta_ids = []
            
            # Buscar PDFs adjuntos para identificar las ventas
            for i in range(50):  # Limitar a 50 archivos como máximo
                pdf_id = request.POST.get(f'pdf_id_{i}')
                if not pdf_id:
                    continue
                try:
                    venta_ids.append(int(pdf_id))
                except (ValueError, TypeError):
                    pass
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Formato incorrecto de IDs de ventas'
        }, status=400)
    
    if not venta_ids:
        return JsonResponse({
            'success': False,
            'error': 'No se seleccionaron albaranes para enviar'
        }, status=400)
    
    # Verificar si hay demasiados albaranes seleccionados
    if len(venta_ids) > 10:
        return JsonResponse({
            'success': False,
            'error': 'Se seleccionaron demasiados albaranes. Por favor, envíe un máximo de 10 albaranes a la vez.'
        }, status=400)
    
    # Obtener la agencia de aduana
    try:
        agencia = AgenciaAduana.objects.get(id=agencia_id)
    except AgenciaAduana.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'La agencia de aduana especificada no existe'
        }, status=404)
    
    # Obtener los correos seleccionados por el usuario
    selected_emails_json = request.POST.get('selected_emails')
    if selected_emails_json:
        try:
            emails = json.loads(selected_emails_json)
            # Asegurar que emails es una lista
            if not isinstance(emails, list):
                emails = []
        except json.JSONDecodeError:
            emails = []
    else:
        # Si no se especificaron correos seleccionados, usar todos los correos de la agencia (comportamiento anterior)
        emails = [agencia.correo] if agencia.correo else []
        if agencia.correos_adicionales:
            # Añadir correos adicionales si existen (separados por coma)
            additional_emails = [email.strip() for email in agencia.correos_adicionales.split(',') if email.strip()]
            emails.extend(additional_emails)
    
    if not emails:
        return JsonResponse({
            'success': False,
            'error': 'No se seleccionaron direcciones de correo electrónico'
        })
    
    # Obtener las ventas para incluir información en el correo
    ventas = Venta.objects.select_related('cliente').filter(id__in=venta_ids)
    if not ventas:
        return JsonResponse({
            'success': False,
            'error': 'No se encontraron las ventas especificadas'
        }, status=404)
    
    # Buscar PDFs adjuntos
    pdf_files = []
    for i in range(50):  # Limitar a 50 archivos como máximo
        pdf_id = request.POST.get(f'pdf_id_{i}')
        pdf_data = request.POST.get(f'pdf_data_{i}')
        
        if not pdf_id or not pdf_data:
            continue
        
        try:
            # Si viene como data URI, extraer solo la parte base64
            if 'base64,' in pdf_data:
                pdf_base64 = pdf_data.split('base64,')[1]
            else:
                pdf_base64 = pdf_data
                
            # Verificar la longitud del PDF antes de decodificar
            if len(pdf_base64) > 5000000:  # Aproximadamente 5MB en base64
                return JsonResponse({
                    'success': False,
                    'error': f'El PDF del albarán #{pdf_id} es demasiado grande. Intente comprimir el PDF o enviar menos albaranes a la vez.'
                }, status=413)  # 413 Payload Too Large
            
            # Decodificar los datos PDF
            try:
                pdf_bytes = base64.b64decode(pdf_base64)
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Error al decodificar el PDF del albarán #{pdf_id}: {str(e)}'
                }, status=400)
            
            # Buscar la venta correspondiente
            venta_id = int(pdf_id)
            venta = next((v for v in ventas if v.id == venta_id), None)
            
            if venta:
                # Añadir a la lista de archivos
                pdf_files.append({
                    'filename': f'Albaran_{venta.id}_{venta.cliente.nombre.replace(" ", "_")}.pdf',
                    'content': pdf_bytes,
                    'venta': venta
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error al procesar el PDF del albarán #{pdf_id}: {str(e)}'
            })
    
    if not pdf_files:
        return JsonResponse({
            'success': False,
            'error': 'No se recibieron datos PDF válidos'
        }, status=400)
    
    # Obtener la fecha de entrega del primer albarán o del albarán actual si está incluido
    fecha_entrega = None
    # Primero buscar si el albarán actual está incluido
    current_venta_id = request.POST.get('current_venta_id')
    if current_venta_id:
        try:
            current_venta_id = int(current_venta_id)
            current_venta = next((pdf['venta'] for pdf in pdf_files if pdf['venta'].id == current_venta_id), None)
            if current_venta and current_venta.fecha_entrega:
                fecha_entrega = current_venta.fecha_entrega
        except (ValueError, TypeError):
            pass
    
    # Si no se encontró fecha con el albarán actual, usar la primera fecha disponible
    if not fecha_entrega and pdf_files:
        for pdf in pdf_files:
            if pdf['venta'].fecha_entrega:
                fecha_entrega = pdf['venta'].fecha_entrega
                break
    
    # Actualizar el asunto con la fecha de entrega si está disponible
    if fecha_entrega:
        email_subject = f"{email_subject} - Fecha: {fecha_entrega.strftime('%d/%m/%Y')}"
    
    # Preparar la información detallada de los albaranes
    ventas_info = []
    for pdf in pdf_files:
        venta = pdf['venta']
        cliente = venta.cliente
        info = f"• Albarán #{venta.id} - Cliente: {cliente.nombre}"
        
        # Añadir dirección y ciudad
        if hasattr(cliente, 'domicilio') and cliente.domicilio:
            info += f"\n  Dirección: {cliente.domicilio}"
        if hasattr(cliente, 'ciudad') and cliente.ciudad:
            info += f"\n  Ciudad: {cliente.ciudad}"
            # No check for pais since it doesn't exist in your model
        
        # Añadir fecha de entrega
        if venta.fecha_entrega:
            info += f"\n  Fecha de entrega: {venta.fecha_entrega.strftime('%d/%m/%Y')}"
            
        ventas_info.append(info)
    
    # Construir el cuerpo del mensaje
    body = f"""
Estimado/a {agencia.nombre},

Adjunto encontrará los siguientes albaranes para trámites de aduana:

{chr(10).join(ventas_info)}

Por favor, proceda con los trámites correspondientes.

Gracias por su colaboración.
"""

    # Añadir mensaje adicional si existe (en lugar de reemplazar)
    if email_message:
        body += f"""

Nota adicional:
{email_message}
"""

    # Añadir firma al final
    body += """

Atentamente,
Luz Mery Melo Mejia
L&M Exotic Fruit
    """
    
    # Crear y enviar el email
    try:
        email = EmailMessage(
            subject=email_subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=emails,
        )
        
        # Adjuntar los PDFs al email
        for pdf_file in pdf_files:
            email.attach(
                pdf_file['filename'],
                pdf_file['content'],
                'application/pdf'
            )
        
        # Enviar el email
        email.send()
        
        return JsonResponse({
            'success': True,
            'emails': ", ".join(emails),
            'message': f'{len(pdf_files)} albarán(es)'
        })
        
    except Exception as e:
        import traceback
        print(f"Error al enviar el email: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'Error al enviar el email: {str(e)}'
        })
