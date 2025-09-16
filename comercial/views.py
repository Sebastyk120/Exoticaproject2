from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from .models import EmailLog
from django.utils import timezone
from datetime import datetime, timedelta


@login_required
def lista_correos(request):
    """
    Vista para mostrar la lista de correos enviados con paginación y filtros
    """
    # Obtener parámetros de filtro
    proceso = request.GET.get('proceso', '')
    estado = request.GET.get('estado', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    buscar = request.GET.get('buscar', '')
    
    # Consulta base
    correos = EmailLog.objects.all().select_related('usuario')
    
    # Aplicar filtros
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
    
    if buscar:
        correos = correos.filter(
            Q(asunto__icontains=buscar) |
            Q(destinatarios__icontains=buscar) |
            Q(usuario__username__icontains=buscar) |
            Q(observaciones__icontains=buscar)
        )
    
    # Ordenar por fecha más reciente
    correos = correos.order_by('-fecha_envio')
    
    # Paginación
    paginator = Paginator(correos, 20)  # 20 correos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas rápidas
    total_correos = EmailLog.objects.count()
    correos_exitosos = EmailLog.objects.filter(estado_envio='exitoso').count()
    correos_fallidos = EmailLog.objects.filter(estado_envio='fallido').count()
    correos_hoy = EmailLog.objects.filter(fecha_envio__date=timezone.now().date()).count()
    
    # Obtener opciones para los filtros
    procesos_disponibles = EmailLog.PROCESO_CHOICES
    estados_disponibles = EmailLog.ESTADO_CHOICES
    
    context = {
        'page_obj': page_obj,
        'correos': page_obj.object_list,
        'total_correos': total_correos,
        'correos_exitosos': correos_exitosos,
        'correos_fallidos': correos_fallidos,
        'correos_hoy': correos_hoy,
        'procesos_disponibles': procesos_disponibles,
        'estados_disponibles': estados_disponibles,
        'filtros': {
            'proceso': proceso,
            'estado': estado,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'buscar': buscar,
        },
        'porcentaje_exito': round((correos_exitosos / total_correos * 100) if total_correos > 0 else 0, 1),
    }
    
    return render(request, 'ventas/correos.html', context)


@login_required
def detalle_correo(request, correo_id):
    """
    Vista AJAX para obtener los detalles de un correo específico
    """
    try:
        correo = EmailLog.objects.select_related('usuario').get(id=correo_id)
        data = {
            'success': True,
            'correo': {
                'id': correo.id,
                'proceso': correo.get_proceso_display(),
                'asunto': correo.asunto,
                'destinatarios': correo.destinatarios,
                'fecha_envio': correo.fecha_envio.strftime('%d/%m/%Y %H:%M:%S'),
                'estado': correo.get_estado_envio_display(),
                'usuario': correo.usuario.username if correo.usuario else 'Sistema',
                'cuerpo_mensaje': correo.cuerpo_mensaje or 'Sin mensaje',
                'mensaje_error': correo.mensaje_error or 'Sin errores',
                'documentos_adjuntos': correo.documentos_adjuntos or 'Sin archivos adjuntos',
            }
        }
    except EmailLog.DoesNotExist:
        data = {
            'success': False,
            'error': 'Correo no encontrado'
        }
    
    return JsonResponse(data)