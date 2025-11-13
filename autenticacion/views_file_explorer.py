import os
import mimetypes
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
    Crea un backup SQL completo de la base de datos.
    Genera un backup SQL real sin depender de herramientas externas como pg_dump.
    Ideal para bases de datos grandes y compatible con Railway.
    
    Args:
        request: HttpRequest object
        
    Returns:
        Redirect a la carpeta de backups con mensaje de éxito o error
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido.")
        return redirect('autenticacion:file_explorer')

    try:
        from django.db import connection, transaction
        from django.core.management.color import no_style
        from io import StringIO
        import gzip
        
        # Crear directorio de backups si no existe
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generar nombre del archivo con timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Obtener nombre de la base de datos desde settings
        db_settings = settings.DATABASES.get('default', {})
        db_name = db_settings.get('NAME', 'database')
        # Limpiar el nombre si viene de una URL
        if '/' in db_name:
            db_name = db_name.split('/')[-1].split('?')[0]
        
        backup_filename = f'backup_{db_name}_{timestamp}.sql.gz'
        backup_filepath = os.path.join(backup_dir, backup_filename)
        
        logger.info(f"Usuario {request.user.username} inició creación de backup SQL: {backup_filename}")
        
        # Contadores para el resumen
        total_tables = 0
        total_records = 0
        total_size = 0
        
        with gzip.open(backup_filepath, 'wt', encoding='utf-8') as backup_file:
            # Escribir header del backup
            backup_file.write(f"-- Backup de {db_name} creado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            backup_file.write(f"-- Generado por Django file_explorer\n")
            backup_file.write(f"-- Usuario: {request.user.username}\n\n")
            
            # Obtener todas las tablas excepto django_migrations
            with connection.cursor() as cursor:
                # Listar todas las tablas
                cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_name NOT IN ('django_migrations', 'django_session')
                    ORDER BY table_name
                """, [connection.settings_dict.get('NAME', 'public')])
                
                tables = [row[0] for row in cursor.fetchall()]
                total_tables = len(tables)
                
                # Escribir SQL para cada tabla
                for table_name in tables:
                    try:
                        # Obtener esquema de la tabla
                        backup_file.write(f"\n-- Estructura de la tabla: {table_name}\n")
                        backup_file.write(f"DROP TABLE IF EXISTS {table_name} CASCADE;\n")
                        
                        # Obtener definición de la tabla
                        cursor.execute("""
                            SELECT column_name, data_type, is_nullable, column_default
                            FROM information_schema.columns
                            WHERE table_name = %s AND table_schema = %s
                            ORDER BY ordinal_position
                        """, [table_name, connection.settings_dict.get('NAME', 'public')])
                        
                        columns = cursor.fetchall()
                        if not columns:
                            continue
                            
                        # Crear tabla
                        column_defs = []
                        for col in columns:
                            col_name, data_type, is_nullable, col_default = col
                            
                            if is_nullable == 'NO' and col_default is None:
                                col_def = f"{col_name} {data_type} NOT NULL"
                            else:
                                col_def = f"{col_name} {data_type}"
                                if col_default:
                                    col_def += f" DEFAULT {col_default}"
                                if is_nullable == 'NO':
                                    col_def += " NOT NULL"
                            
                            column_defs.append(col_def)
                        
                        backup_file.write(f"CREATE TABLE {table_name} (\n")
                        backup_file.write("    " + ",\n    ".join(column_defs))
                        backup_file.write("\n);\n")
                        
                        # Obtener índices
                        cursor.execute("""
                            SELECT indexname, indexdef
                            FROM pg_indexes
                            WHERE tablename = %s AND schemaname = %s
                        """, [table_name, connection.settings_dict.get('NAME', 'public')])
                        
                        indexes = cursor.fetchall()
                        for idx_name, idx_def in indexes:
                            if idx_name != f"{table_name}_pkey":  # Excluir PK que ya está en CREATE TABLE
                                backup_file.write(f"\n{idx_def};\n")
                        
                        # Obtener datos de la tabla
                        cursor.execute(f"SELECT * FROM {table_name}")
                        rows = cursor.fetchall()
                        
                        if rows:
                            backup_file.write(f"\n-- Datos de la tabla: {table_name} ({len(rows)} registros)\n")
                            
                            # Escribir INSERT statements en lotes
                            batch_size = 1000
                            for i in range(0, len(rows), batch_size):
                                batch = rows[i:i + batch_size]
                                backup_file.write(f"INSERT INTO {table_name} (")
                                
                                # Columnas
                                column_names = [col[0] for col in columns]
                                backup_file.write(", ".join(column_names))
                                backup_file.write(") VALUES\n")
                                
                                # Valores
                                values_lines = []
                                for row in batch:
                                    values = []
                                    for value in row:
                                        if value is None:
                                            values.append("NULL")
                                        elif isinstance(value, str):
                                            # Escapar comillas simples
                                            escaped_value = value.replace("'", "''")
                                            values.append(f"'{escaped_value}'")
                                        elif isinstance(value, bool):
                                            values.append("TRUE" if value else "FALSE")
                                        elif isinstance(value, (int, float)):
                                            values.append(str(value))
                                        else:
                                            # Otros tipos de datos
                                            escaped_value = str(value).replace("'", "''")
                                            values.append(f"'{escaped_value}'")
                                    
                                    values_lines.append(f"    ({', '.join(values)})")
                                
                                backup_file.write(",\n".join(values_lines))
                                backup_file.write(";\n\n")
                                
                                # Actualizar contador
                                total_records += len(batch)
                        
                        logger.info(f"Backup de tabla {table_name} completado: {len(rows)} registros")
                        
                    except Exception as table_error:
                        logger.error(f"Error al hacer backup de la tabla {table_name}: {str(table_error)}")
                        backup_file.write(f"\n-- ERROR en la tabla {table_name}: {str(table_error)}\n")
                        continue
            
            # Escribir footer
            backup_file.write(f"\n-- Backup completado: {total_tables} tablas, {total_records} registros totales\n")
            backup_file.write(f"-- Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Verificar que el archivo fue creado y tiene contenido
        if os.path.exists(backup_filepath) and os.path.getsize(backup_filepath) > 0:
            file_size = format_file_size(os.path.getsize(backup_filepath))
            total_size = os.path.getsize(backup_filepath)
            
            messages.success(
                request,
                f"Backup SQL '{backup_filename}' creado exitosamente: {total_records} registros, {file_size} en /media/backups/"
            )
            logger.info(f"Backup SQL creado exitosamente: {backup_filename} con {total_records} registros ({file_size})")
        else:
            messages.warning(request, "El backup se completó pero el archivo está vacío o no fue creado.")
            logger.warning(f"Backup completado pero archivo vacío o no existe: {backup_filepath}")
    
    except Exception as e:
        logger.error(f"Error inesperado al crear backup SQL: {str(e)}", exc_info=True)
        messages.error(request, f"Ocurrió un error inesperado al crear el backup SQL: {str(e)}")

    return redirect('autenticacion:file_explorer_subpath', subpath='backups')
    