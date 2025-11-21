import os
import mimetypes
import shutil
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import user_passes_test
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.contrib import messages
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)


def get_safe_path(requested_path):
    """
    Valida que la ruta solicitada esté dentro de MEDIA_ROOT
    y previene ataques de path traversal.
    
    Args:
        requested_path: Ruta relativa solicitada por el usuario
        
    Returns:
        str: Ruta absoluta validada
        
    Raises:
        PermissionDenied: Si la ruta está fuera de MEDIA_ROOT
    """
    # Obtener la ruta base de media
    base_path = os.path.realpath(settings.MEDIA_ROOT)
    
    # Construir la ruta completa y normalizarla
    if requested_path:
        full_path = os.path.realpath(os.path.join(base_path, requested_path))
    else:
        full_path = base_path
    
    # Verificar que la ruta está dentro de MEDIA_ROOT
    if not full_path.startswith(base_path):
        logger.warning(f"Intento de acceso no autorizado a: {requested_path}")
        raise PermissionDenied("Acceso denegado a esta ruta")
    
    return full_path


def get_file_icon(filename):
    """
    Retorna el icono FontAwesome apropiado según la extensión del archivo.
    
    Args:
        filename: Nombre del archivo
        
    Returns:
        str: Clase CSS del icono FontAwesome
    """
    ext = os.path.splitext(filename)[1].lower()
    
    icon_map = {
        # Documentos
        '.pdf': 'fa-file-pdf text-danger',
        '.doc': 'fa-file-word text-primary',
        '.docx': 'fa-file-word text-primary',
        '.txt': 'fa-file-alt text-secondary',
        
        # Hojas de cálculo
        '.xls': 'fa-file-excel text-success',
        '.xlsx': 'fa-file-excel text-success',
        '.csv': 'fa-file-csv text-success',
        
        # Imágenes
        '.jpg': 'fa-file-image text-success',
        '.jpeg': 'fa-file-image text-success',
        '.png': 'fa-file-image text-success',
        '.gif': 'fa-file-image text-success',
        '.svg': 'fa-file-image text-success',
        '.bmp': 'fa-file-image text-success',
        '.webp': 'fa-file-image text-success',
        
        # Archivos comprimidos
        '.zip': 'fa-file-archive text-warning',
        '.rar': 'fa-file-archive text-warning',
        '.7z': 'fa-file-archive text-warning',
        '.tar': 'fa-file-archive text-warning',
        '.gz': 'fa-file-archive text-warning',
        
        # Código
        '.py': 'fa-file-code text-info',
        '.js': 'fa-file-code text-warning',
        '.html': 'fa-file-code text-danger',
        '.css': 'fa-file-code text-primary',
        '.json': 'fa-file-code text-success',
        '.xml': 'fa-file-code text-warning',
    }
    
    return icon_map.get(ext, 'fa-file text-secondary')


def format_file_size(size_bytes):
    """
    Formatea el tamaño del archivo en formato legible.
    
    Args:
        size_bytes: Tamaño en bytes
        
    Returns:
        str: Tamaño formateado (ej: "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


@user_passes_test(lambda u: u.is_superuser, login_url='/app/login/')
def file_explorer_view(request, subpath=''):
    """
    Vista principal del explorador de archivos.
    Muestra el contenido del directorio actual (carpetas y archivos).
    
    Args:
        request: HttpRequest object
        subpath: Ruta relativa dentro de MEDIA_ROOT
        
    Returns:
        HttpResponse con el template renderizado
    """
    try:
        # Validar y obtener la ruta segura
        current_path = get_safe_path(subpath)
        
        # Verificar que el path existe
        if not os.path.exists(current_path):
            messages.error(request, f"La ruta no existe: {subpath}")
            return redirect('autenticacion:file_explorer')
        
        # Verificar que es un directorio
        if not os.path.isdir(current_path):
            messages.error(request, "La ruta especificada no es un directorio")
            return redirect('autenticacion:file_explorer')
        
        # Listar contenido del directorio
        items = []
        try:
            for item_name in sorted(os.listdir(current_path)):
                item_path = os.path.join(current_path, item_name)
                
                # Obtener información del item
                is_dir = os.path.isdir(item_path)
                
                # Construir la ruta relativa para los enlaces
                if subpath:
                    relative_path = os.path.join(subpath, item_name).replace('\\', '/')
                else:
                    relative_path = item_name
                
                item_info = {
                    'name': item_name,
                    'is_dir': is_dir,
                    'relative_path': relative_path,
                }
                
                if is_dir:
                    item_info['icon'] = 'fa-folder text-primary'
                    item_info['size'] = '-'
                    item_info['type'] = 'Carpeta'
                else:
                    # Información del archivo
                    item_info['icon'] = get_file_icon(item_name)
                    item_info['size'] = format_file_size(os.path.getsize(item_path))
                    item_info['type'] = 'Archivo'
                
                # Fecha de modificación
                mtime = os.path.getmtime(item_path)
                item_info['modified'] = datetime.fromtimestamp(mtime).strftime('%d/%m/%Y %H:%M')
                
                items.append(item_info)
                
        except PermissionError:
            messages.error(request, "No tienes permisos para acceder a esta carpeta")
            return redirect('autenticacion:file_explorer')
        
        # Crear breadcrumb para navegación
        breadcrumbs = [{'name': 'Media', 'path': ''}]
        if subpath:
            parts = subpath.split('/')
            current = ''
            for part in parts:
                if part:  # Evitar partes vacías
                    current = os.path.join(current, part).replace('\\', '/')
                    breadcrumbs.append({'name': part, 'path': current})
        
        # Obtener el directorio padre para el botón "Volver"
        parent_path = ''
        if subpath:
            parent_path = os.path.dirname(subpath).replace('\\', '/')
        
        context = {
            'items': items,
            'current_path': subpath or 'Media',
            'current_subpath': subpath,  # Ruta actual para los formularios
            'breadcrumbs': breadcrumbs,
            'parent_path': parent_path,
            'has_parent': bool(subpath),
        }
        
        return render(request, 'file_explorer.html', context)
        
    except PermissionDenied as e:
        messages.error(request, str(e))
        return redirect('autenticacion:file_explorer')
    except Exception as e:
        logger.error(f"Error en file_explorer_view: {str(e)}")
        messages.error(request, "Ocurrió un error al acceder al explorador de archivos")
        return redirect('autenticacion:home')


@user_passes_test(lambda u: u.is_superuser, login_url='/app/login/')
def download_file(request, file_path):
    """
    Vista para descargar un archivo.
    
    Args:
        request: HttpRequest object
        file_path: Ruta relativa del archivo dentro de MEDIA_ROOT
        
    Returns:
        FileResponse con el archivo para descargar
    """
    try:
        # Validar y obtener la ruta segura
        full_path = get_safe_path(file_path)
        
        # Verificar que el archivo existe
        if not os.path.exists(full_path):
            messages.error(request, "El archivo no existe")
            raise Http404("Archivo no encontrado")
        
        # Verificar que es un archivo (no un directorio)
        if not os.path.isfile(full_path):
            messages.error(request, "La ruta especificada no es un archivo")
            return redirect('autenticacion:file_explorer')
        
        # Obtener el tipo MIME del archivo
        content_type, _ = mimetypes.guess_type(full_path)
        if content_type is None:
            content_type = 'application/octet-stream'
        
        # Abrir el archivo y crear la respuesta
        file_handle = open(full_path, 'rb')
        response = FileResponse(file_handle, content_type=content_type)
        
        # Establecer el nombre del archivo para la descarga
        filename = os.path.basename(full_path)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        logger.info(f"Usuario {request.user.username} descargó el archivo: {file_path}")
        
        return response
        
    except PermissionDenied as e:
        messages.error(request, str(e))
        return redirect('autenticacion:file_explorer')
    except Exception as e:
        logger.error(f"Error al descargar archivo {file_path}: {str(e)}")
        messages.error(request, "Ocurrió un error al descargar el archivo")
        return redirect('autenticacion:file_explorer')


@user_passes_test(lambda u: u.is_superuser, login_url='/app/login/')
def delete_file(request, file_path):
    """
    Vista para eliminar un archivo.
    Requiere método POST con token CSRF.
    
    Args:
        request: HttpRequest object
        file_path: Ruta relativa del archivo dentro de MEDIA_ROOT
        
    Returns:
        Redirect a la carpeta padre después de eliminar
    """
    # Solo permitir método POST
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('autenticacion:file_explorer')
    
    try:
        # Validar y obtener la ruta segura
        full_path = get_safe_path(file_path)
        
        # Verificar que el archivo existe
        if not os.path.exists(full_path):
            messages.error(request, "El archivo no existe")
            return redirect('autenticacion:file_explorer')
        
        # Verificar que es un archivo (no un directorio)
        if not os.path.isfile(full_path):
            messages.error(request, "Solo se pueden eliminar archivos, no directorios")
            parent_dir = os.path.dirname(file_path).replace('\\', '/')
            if parent_dir:
                return redirect('autenticacion:file_explorer_subpath', subpath=parent_dir)
            return redirect('autenticacion:file_explorer')
        
        # Obtener el nombre del archivo antes de eliminarlo
        filename = os.path.basename(full_path)
        
        # Eliminar el archivo
        os.remove(full_path)
        
        # Log de la operación
        logger.warning(f"Usuario {request.user.username} eliminó el archivo: {file_path}")
        
        messages.success(request, f"El archivo '{filename}' ha sido eliminado correctamente")
        
        # Redirigir a la carpeta padre
        parent_dir = os.path.dirname(file_path).replace('\\', '/')
        if parent_dir:
            return redirect('autenticacion:file_explorer_subpath', subpath=parent_dir)
        return redirect('autenticacion:file_explorer')
        
    except PermissionDenied as e:
        messages.error(request, str(e))
        return redirect('autenticacion:file_explorer')
    except PermissionError:
        messages.error(request, "No tienes permisos para eliminar este archivo")
        parent_dir = os.path.dirname(file_path).replace('\\', '/')
        if parent_dir:
            return redirect('autenticacion:file_explorer_subpath', subpath=parent_dir)
        return redirect('autenticacion:file_explorer')
    except Exception as e:
        logger.error(f"Error al eliminar archivo {file_path}: {str(e)}")
        messages.error(request, "Ocurrió un error al eliminar el archivo")
        parent_dir = os.path.dirname(file_path).replace('\\', '/')
        if parent_dir:
            return redirect('autenticacion:file_explorer_subpath', subpath=parent_dir)
        return redirect('autenticacion:file_explorer')


@user_passes_test(lambda u: u.is_superuser, login_url='/app/login/')
def create_backup(request):
    """
    Crea un backup de la base de datos PostgreSQL utilizando DATABASE_URL.
    
    Args:
        request: HttpRequest object
        
    Returns:
        Redirect a la carpeta de backups con mensaje de éxito o error
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido.")
        return redirect('autenticacion:file_explorer')

    try:
        import subprocess
        
        # Obtener DATABASE_URL desde las variables de entorno
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            messages.error(request, "DATABASE_URL no está configurada en las variables de entorno.")
            logger.error("DATABASE_URL no encontrada al intentar crear backup")
            return redirect('autenticacion:file_explorer')
        
        # Verificar que sea una base de datos PostgreSQL
        if not database_url.startswith(('postgres://', 'postgresql://')):
            messages.error(request, "La funcionalidad de backup solo está disponible para bases de datos PostgreSQL.")
            logger.warning(f"Intento de backup con base de datos no PostgreSQL: {database_url[:20]}...")
            return redirect('autenticacion:file_explorer')
        
        # Crear directorio de backups si no existe
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generar nombre del archivo con timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Extraer nombre de la base de datos desde DATABASE_URL para el nombre del archivo
        # Formato: postgres://user:pass@host:port/dbname
        try:
            db_name = database_url.split('/')[-1].split('?')[0]  # Obtener dbname
        except:
            db_name = 'database'  # Fallback si no se puede extraer
        
        backup_filename = f'backup_{db_name}_{timestamp}.backup'
        backup_filepath = os.path.join(backup_dir, backup_filename)
        
        # Construir el comando pg_dump usando DATABASE_URL directamente
        command = [
            'pg_dump',
            '--dbname', database_url,
            '-f', backup_filepath,
            '--format=c',  # custom format, compressed
            '--verbose',
        ]
        
        logger.info(f"Usuario {request.user.username} inició creación de backup: {backup_filename}")
        
        # Ejecutar pg_dump
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False  # No lanzar excepción en error para manejarlo manualmente
        )
        
        if process.returncode == 0:
            # Verificar que el archivo fue creado y tiene contenido
            if os.path.exists(backup_filepath) and os.path.getsize(backup_filepath) > 0:
                file_size = format_file_size(os.path.getsize(backup_filepath))
                messages.success(
                    request,
                    f"Backup '{backup_filename}' creado exitosamente ({file_size}) en /media/backups/."
                )
                logger.info(f"Backup creado exitosamente: {backup_filename} ({file_size})")
            else:
                messages.warning(request, "El backup se completó pero el archivo está vacío o no fue creado.")
                logger.warning(f"Backup completado pero archivo vacío o no existe: {backup_filepath}")
        else:
            # Capturar y registrar el error
            error_message = process.stderr or process.stdout or "Error desconocido"
            logger.error(f"Error al crear backup para usuario {request.user.username}: {error_message}")
            messages.error(request, f"Error al crear el backup. Consulte los logs para más detalles.")
    
    except subprocess.TimeoutExpired:
        logger.error("Timeout al ejecutar pg_dump")
        messages.error(request, "El proceso de backup tardó demasiado y fue cancelado.")
    except FileNotFoundError:
        logger.error("pg_dump no encontrado en el sistema")
        messages.error(
            request,
            "No se encontró el comando 'pg_dump'. Asegúrese de que PostgreSQL está instalado y en el PATH."
        )
    except Exception as e:
        logger.error(f"Error inesperado al crear backup: {str(e)}", exc_info=True)
        messages.error(request, f"Ocurrió un error inesperado al crear el backup.")

    return redirect('autenticacion:file_explorer_subpath', subpath='backups')


@user_passes_test(lambda u: u.is_superuser, login_url='/app/login/')
def delete_folder(request, folder_path):
    """
    Vista para eliminar una carpeta completa y todo su contenido.
    Requiere método POST con token CSRF.

    Args:
        request: HttpRequest object
        folder_path: Ruta relativa de la carpeta dentro de MEDIA_ROOT

    Returns:
        Redirect a la carpeta padre después de eliminar
    """
    # Solo permitir método POST
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('autenticacion:file_explorer')

    try:
        # Validar y obtener la ruta segura
        full_path = get_safe_path(folder_path)

        # Verificar que la carpeta existe
        if not os.path.exists(full_path):
            messages.error(request, "La carpeta no existe")
            return redirect('autenticacion:file_explorer')

        # Verificar que es un directorio (no un archivo)
        if not os.path.isdir(full_path):
            messages.error(request, "La ruta especificada no es una carpeta")
            parent_dir = os.path.dirname(folder_path).replace('\\', '/')
            if parent_dir:
                return redirect('autenticacion:file_explorer_subpath', subpath=parent_dir)
            return redirect('autenticacion:file_explorer')

        # Prevenir eliminación del directorio raíz de media
        if full_path == os.path.realpath(settings.MEDIA_ROOT):
            messages.error(request, "No se puede eliminar el directorio raíz de media")
            return redirect('autenticacion:file_explorer')

        # Obtener el nombre de la carpeta antes de eliminarla
        foldername = os.path.basename(full_path)

        # Contar archivos y subcarpetas para informar al usuario
        total_items = sum([len(files) + len(dirs) for _, dirs, files in os.walk(full_path)])

        # Eliminar la carpeta y todo su contenido
        shutil.rmtree(full_path)

        # Log de la operación
        logger.warning(f"Usuario {request.user.username} eliminó la carpeta: {folder_path} ({total_items} elementos)")

        messages.success(request, f"La carpeta '{foldername}' y todo su contenido ({total_items} elementos) han sido eliminados correctamente")

        # Redirigir a la carpeta padre
        parent_dir = os.path.dirname(folder_path).replace('\\', '/')
        if parent_dir:
            return redirect('autenticacion:file_explorer_subpath', subpath=parent_dir)
        return redirect('autenticacion:file_explorer')

    except PermissionDenied as e:
        messages.error(request, str(e))
        return redirect('autenticacion:file_explorer')
    except PermissionError:
        messages.error(request, "No tienes permisos para eliminar esta carpeta")
        parent_dir = os.path.dirname(folder_path).replace('\\', '/')
        if parent_dir:
            return redirect('autenticacion:file_explorer_subpath', subpath=parent_dir)
        return redirect('autenticacion:file_explorer')
    except Exception as e:
        logger.error(f"Error al eliminar carpeta {folder_path}: {str(e)}")
        messages.error(request, "Ocurrió un error al eliminar la carpeta")
        parent_dir = os.path.dirname(folder_path).replace('\\', '/')
        if parent_dir:
            return redirect('autenticacion:file_explorer_subpath', subpath=parent_dir)
        return redirect('autenticacion:file_explorer')


@user_passes_test(lambda u: u.is_superuser, login_url='/app/login/')
def create_folder(request):
    """
    Vista para crear una nueva carpeta.
    Requiere método POST con token CSRF.

    Args:
        request: HttpRequest object con 'folder_name' y 'current_path' en POST

    Returns:
        Redirect a la carpeta actual después de crear
    """
    # Solo permitir método POST
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('autenticacion:file_explorer')

    try:
        folder_name = request.POST.get('folder_name', '').strip()
        current_path = request.POST.get('current_path', '').strip()

        # Validar que se proporcionó un nombre
        if not folder_name:
            messages.error(request, "Debes proporcionar un nombre para la carpeta")
            if current_path:
                return redirect('autenticacion:file_explorer_subpath', subpath=current_path)
            return redirect('autenticacion:file_explorer')

        # Validar caracteres no permitidos en el nombre
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in folder_name for char in invalid_chars):
            messages.error(request, f"El nombre de la carpeta no puede contener los siguientes caracteres: {' '.join(invalid_chars)}")
            if current_path:
                return redirect('autenticacion:file_explorer_subpath', subpath=current_path)
            return redirect('autenticacion:file_explorer')

        # Construir la ruta completa de la nueva carpeta
        if current_path:
            new_folder_relative = os.path.join(current_path, folder_name).replace('\\', '/')
        else:
            new_folder_relative = folder_name

        # Validar y obtener la ruta segura
        new_folder_path = get_safe_path(new_folder_relative)

        # Verificar que la carpeta no existe ya
        if os.path.exists(new_folder_path):
            messages.error(request, f"Ya existe una carpeta o archivo con el nombre '{folder_name}'")
            if current_path:
                return redirect('autenticacion:file_explorer_subpath', subpath=current_path)
            return redirect('autenticacion:file_explorer')

        # Crear la carpeta
        os.makedirs(new_folder_path)

        # Log de la operación
        logger.info(f"Usuario {request.user.username} creó la carpeta: {new_folder_relative}")

        messages.success(request, f"La carpeta '{folder_name}' ha sido creada correctamente")

        # Redirigir a la carpeta actual
        if current_path:
            return redirect('autenticacion:file_explorer_subpath', subpath=current_path)
        return redirect('autenticacion:file_explorer')

    except PermissionDenied as e:
        messages.error(request, str(e))
        return redirect('autenticacion:file_explorer')
    except PermissionError:
        messages.error(request, "No tienes permisos para crear carpetas en esta ubicación")
        current_path = request.POST.get('current_path', '').strip()
        if current_path:
            return redirect('autenticacion:file_explorer_subpath', subpath=current_path)
        return redirect('autenticacion:file_explorer')
    except Exception as e:
        logger.error(f"Error al crear carpeta: {str(e)}")
        messages.error(request, "Ocurrió un error al crear la carpeta")
        current_path = request.POST.get('current_path', '').strip()
        if current_path:
            return redirect('autenticacion:file_explorer_subpath', subpath=current_path)
        return redirect('autenticacion:file_explorer')


@user_passes_test(lambda u: u.is_superuser, login_url='/app/login/')
def upload_file(request):
    """
    Vista para subir un archivo a la carpeta actual.
    Requiere método POST con token CSRF.
    Acepta cualquier tipo de archivo sin limitaciones.

    Args:
        request: HttpRequest object con 'file' y 'current_path' en POST

    Returns:
        Redirect a la carpeta actual después de subir
    """
    # Solo permitir método POST
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('autenticacion:file_explorer')

    try:
        uploaded_file = request.FILES.get('file')
        current_path = request.POST.get('current_path', '').strip()

        # Validar que se proporcionó un archivo
        if not uploaded_file:
            messages.error(request, "Debes seleccionar un archivo para subir")
            if current_path:
                return redirect('autenticacion:file_explorer_subpath', subpath=current_path)
            return redirect('autenticacion:file_explorer')

        # Obtener el nombre del archivo
        filename = uploaded_file.name

        # Construir la ruta completa del archivo
        if current_path:
            file_relative_path = os.path.join(current_path, filename).replace('\\', '/')
        else:
            file_relative_path = filename

        # Validar y obtener la ruta segura
        file_full_path = get_safe_path(file_relative_path)

        # Verificar si el archivo ya existe
        if os.path.exists(file_full_path):
            # Generar un nombre único agregando un número
            base_name, extension = os.path.splitext(filename)
            counter = 1
            while os.path.exists(file_full_path):
                new_filename = f"{base_name}_{counter}{extension}"
                if current_path:
                    file_relative_path = os.path.join(current_path, new_filename).replace('\\', '/')
                else:
                    file_relative_path = new_filename
                file_full_path = get_safe_path(file_relative_path)
                counter += 1
            filename = new_filename
            messages.warning(request, f"El archivo fue renombrado a '{filename}' porque ya existía un archivo con ese nombre")

        # Guardar el archivo
        with open(file_full_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # Obtener el tamaño del archivo para el mensaje
        file_size = format_file_size(os.path.getsize(file_full_path))

        # Log de la operación
        logger.info(f"Usuario {request.user.username} subió el archivo: {file_relative_path} ({file_size})")

        messages.success(request, f"El archivo '{filename}' ({file_size}) ha sido subido correctamente")

        # Redirigir a la carpeta actual
        if current_path:
            return redirect('autenticacion:file_explorer_subpath', subpath=current_path)
        return redirect('autenticacion:file_explorer')

    except PermissionDenied as e:
        messages.error(request, str(e))
        return redirect('autenticacion:file_explorer')
    except PermissionError:
        messages.error(request, "No tienes permisos para subir archivos en esta ubicación")
        current_path = request.POST.get('current_path', '').strip()
        if current_path:
            return redirect('autenticacion:file_explorer_subpath', subpath=current_path)
        return redirect('autenticacion:file_explorer')
    except Exception as e:
        logger.error(f"Error al subir archivo: {str(e)}")
        messages.error(request, "Ocurrió un error al subir el archivo")
        current_path = request.POST.get('current_path', '').strip()
        if current_path:
            return redirect('autenticacion:file_explorer_subpath', subpath=current_path)
        return redirect('autenticacion:file_explorer')
