from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.core.files.storage import default_storage
from django.conf import settings
from django.views.decorators.http import require_http_methods
import os
import logging
import mimetypes
from .models import EmailLog

logger = logging.getLogger(__name__)

@login_required
@require_http_methods(["GET"])
def descargar_adjunto_correo(request, email_log_id, filename):
    """
    Vista para descargar archivos adjuntos de correos de forma segura.
    Valida que el usuario tenga permisos para descargar el archivo.
    """
    try:
        # Obtener el registro de EmailLog
        email_log = EmailLog.objects.get(id=email_log_id)
        
        # Validar que el usuario sea staff o el propietario del correo
        if not request.user.is_staff and email_log.usuario != request.user:
            return JsonResponse({
                'success': False,
                'error': 'No tiene permisos para descargar este archivo'
            }, status=403)
        
        # Buscar el archivo en los campos adjunto_1 a adjunto_5
        adjunto_field = None
        for i in range(1, 6):
            field = getattr(email_log, f'adjunto_{i}', None)
            if field and field.name:
                # Comparar el nombre del archivo
                if field.name.endswith(filename) or field.name.split('/')[-1] == filename:
                    adjunto_field = field
                    break
        
        # Si no se encontró el archivo
        if not adjunto_field:
            logger.warning(f"Archivo no encontrado en campos adjunto: {filename}")
            logger.warning(f"email_log_id: {email_log_id}")
            # Mostrar qué adjuntos existen para debugging
            adjuntos_disponibles = []
            for i in range(1, 6):
                field = getattr(email_log, f'adjunto_{i}', None)
                if field and field.name:
                    adjuntos_disponibles.append(field.name)
            logger.warning(f"Adjuntos disponibles: {adjuntos_disponibles}")
            return JsonResponse({
                'success': False,
                'error': 'Archivo no encontrado'
            }, status=404)
        
        # Validar que el archivo existe físicamente
        if not adjunto_field.storage.exists(adjunto_field.name):
            logger.error(f"El archivo existe en BD pero no en disco: {adjunto_field.name}")
            return JsonResponse({
                'success': False,
                'error': 'El archivo no existe en el servidor'
            }, status=404)
        
        # Obtener la ruta absoluta del archivo
        file_path = adjunto_field.path
        
        # Validar que el archivo está dentro de MEDIA_ROOT (prevenir directory traversal)
        media_root = os.path.abspath(settings.MEDIA_ROOT)
        if not os.path.abspath(file_path).startswith(media_root):
            logger.error(f"Intento de acceso fuera de MEDIA_ROOT: {file_path}")
            return JsonResponse({
                'success': False,
                'error': 'Acceso denegado'
            }, status=403)
        
        # Determinar el tipo MIME
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'application/octet-stream'
        
        # Abrir y retornar el archivo
        # FileResponse se encarga de cerrar el archivo automáticamente
        file_handle = open(file_path, 'rb')
        response = FileResponse(file_handle, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except EmailLog.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'El registro de correo no existe'
        }, status=404)
    except Exception as e:
        logger.error(f"Error descargando adjunto: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'Error al descargar el archivo: {str(e)}'
        }, status=500)


@login_required
def lista_correos(request):
    """
    Vista para listar todos los correos electrónicos enviados
    """
    from django.core.paginator import Paginator
    from django.db.models import Q
    from datetime import datetime
    
    # Obtener parámetros de filtro
    buscar = request.GET.get('buscar', '')
    proceso = request.GET.get('proceso', '')
    estado = request.GET.get('estado', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    # Construir query base
    correos = EmailLog.objects.all()
    
    # Aplicar filtros
    if buscar:
        correos = correos.filter(
            Q(asunto__icontains=buscar) |
            Q(destinatarios__icontains=buscar) |
            Q(usuario__username__icontains=buscar)
        )
    
    if proceso:
        correos = correos.filter(proceso=proceso)
    
    if estado:
        correos = correos.filter(estado_envio=estado)
    
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d')
            correos = correos.filter(fecha_envio__date__gte=fecha_desde_obj.date())
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d')
            correos = correos.filter(fecha_envio__date__lte=fecha_hasta_obj.date())
        except ValueError:
            pass
    
    # Ordenar por fecha descendente
    correos = correos.order_by('-fecha_envio')
    
    # Paginar
    paginator = Paginator(correos, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Calcular estadísticas
    total_correos = EmailLog.objects.count()
    correos_exitosos = EmailLog.objects.filter(estado_envio='exitoso').count()
    correos_fallidos = EmailLog.objects.filter(estado_envio='fallido').count()
    
    from django.utils import timezone
    hoy = timezone.now().date()
    correos_hoy = EmailLog.objects.filter(fecha_envio__date=hoy).count()
    
    # Opciones disponibles
    procesos_disponibles = EmailLog.PROCESO_CHOICES
    estados_disponibles = EmailLog.ESTADO_CHOICES
    
    # Filtros actuales
    filtros = {
        'buscar': buscar,
        'proceso': proceso,
        'estado': estado,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    }
    
    context = {
        'correos': page_obj,
        'page_obj': page_obj,
        'total_correos': total_correos,
        'correos_exitosos': correos_exitosos,
        'correos_fallidos': correos_fallidos,
        'correos_hoy': correos_hoy,
        'procesos_disponibles': procesos_disponibles,
        'estados_disponibles': estados_disponibles,
        'filtros': filtros,
    }
    
    return render(request, 'ventas/correos.html', context)


@login_required
def detalle_correo(request, correo_id):
    """
    Vista AJAX para obtener detalles de un correo específico
    """
    try:
        correo = EmailLog.objects.get(id=correo_id)
        
        # Obtener lista de adjuntos
        adjuntos = correo.get_adjuntos_list()
        
        # Construir URLs de descarga para cada adjunto
        adjuntos_con_url = []
        for adjunto in adjuntos:
            adjuntos_con_url.append({
                'nombre': adjunto['nombre'],
                'url': f'/comercial/correos/descargar/{correo_id}/{adjunto["nombre"]}/'
            })
        
        data = {
            'success': True,
            'correo': {
                'id': correo.id,
                'proceso': correo.get_proceso_display(),
                'estado_envio': correo.estado_envio,
                'fecha_envio': correo.fecha_envio.strftime('%d/%m/%Y %H:%M:%S'),
                'usuario': correo.usuario.username if correo.usuario else 'Sistema',
                'asunto': correo.asunto,
                'destinatarios': correo.destinatarios,
                'cuerpo_mensaje': correo.cuerpo_mensaje,
                'documentos_adjuntos': f'{len(adjuntos)} archivo(s)' if adjuntos else 'Sin archivos',
                'adjuntos': adjuntos_con_url,
                'mensaje_error': correo.mensaje_error or 'Sin errores',
            }
        }
        return JsonResponse(data)
    except EmailLog.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'El correo no existe'
        }, status=404)
    except Exception as e:
        logger.error(f"Error obteniendo detalles del correo: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Error: {str(e)}'
        }, status=500)
