# Explorador de Archivos Web - Documentación

## 📋 Descripción General

El Explorador de Archivos Web es una herramienta administrativa que permite a los superusuarios del sistema gestionar los archivos almacenados en el directorio `/media/` del proyecto Django L&M Exotic Fruits.

## ✨ Características Principales

### Funcionalidades Implementadas

1. **Navegación de Directorios**
   - Exploración completa del árbol de directorios dentro de `/media/`
   - Breadcrumb navigation para visualizar la ruta actual
   - Botón "Volver" para retroceder en la navegación
   - Visualización de carpetas y archivos con iconos diferenciados

2. **Gestión de Archivos**
   - **Descarga**: Descarga individual de cualquier archivo
   - **Eliminación**: Borrado de archivos con confirmación previa
   - **Visualización**: Información detallada (nombre, tamaño, fecha de modificación)

3. **Interfaz de Usuario**
   - Diseño moderno y responsive con Bootstrap 5
   - Iconos FontAwesome diferenciados por tipo de archivo
   - Modal de confirmación para operaciones destructivas
   - Mensajes de feedback (éxito, error, advertencia)
   - Tabla ordenada y fácil de navegar

## 🔒 Seguridad

### Control de Acceso

**Nivel de Restricción**: Solo superusuarios (`is_superuser=True`)

```python
@user_passes_test(lambda u: u.is_superuser, login_url='/app/login/')
```

- Usuarios sin privilegios son redirigidos automáticamente al login
- Usuarios staff (no superusuarios) no tienen acceso
- Todas las vistas están protegidas con este decorador

### Prevención de Path Traversal

El sistema implementa validación estricta de rutas para prevenir ataques de path traversal:

```python
def get_safe_path(requested_path):
    """Valida que la ruta esté dentro de MEDIA_ROOT"""
    base_path = os.path.realpath(settings.MEDIA_ROOT)
    full_path = os.path.realpath(os.path.join(base_path, requested_path))
    
    if not full_path.startswith(base_path):
        raise PermissionDenied("Acceso denegado a esta ruta")
    
    return full_path
```

**Protección contra:**
- Acceso a directorios fuera de `/media/` (ej: `../../etc/passwd`)
- Manipulación de URLs con rutas maliciosas
- Traversal usando symlinks

### CSRF Protection

- Tokens CSRF en todos los formularios POST
- Validación automática de Django para operaciones destructivas
- Método POST requerido para eliminación de archivos

### Logging de Operaciones

Todas las operaciones críticas se registran:

```python
# Descarga de archivos
logger.info(f"Usuario {request.user.username} descargó: {file_path}")

# Eliminación de archivos
logger.warning(f"Usuario {request.user.username} eliminó: {file_path}")
```

## 🏗️ Arquitectura

### Estructura de Archivos

```
autenticacion/
├── views_file_explorer.py      # Lógica backend del explorador
├── urls.py                      # Rutas URL configuradas
├── templates/
│   └── file_explorer.html      # Template principal
└── static/
    └── css/
        └── file_explorer.css   # Estilos personalizados
```

### Vistas Implementadas

#### 1. `file_explorer_view(request, subpath='')`
**Propósito**: Vista principal que lista el contenido de un directorio

**Parámetros**:
- `subpath`: Ruta relativa dentro de `/media/`

**Funcionalidad**:
- Lista archivos y carpetas del directorio actual
- Genera breadcrumb navigation
- Obtiene información de cada item (tamaño, fecha, tipo)
- Maneja errores de permisos y rutas inexistentes

#### 2. `download_file(request, file_path)`
**Propósito**: Descarga un archivo específico

**Parámetros**:
- `file_path`: Ruta relativa del archivo

**Funcionalidad**:
- Valida la ruta del archivo
- Detecta el tipo MIME automáticamente
- Retorna FileResponse para descarga eficiente
- Establece headers apropiados (Content-Disposition)

#### 3. `delete_file(request, file_path)`
**Propósito**: Elimina un archivo (solo POST)

**Parámetros**:
- `file_path`: Ruta relativa del archivo

**Funcionalidad**:
- Valida método POST y token CSRF
- Verifica que es archivo (no directorio)
- Elimina el archivo del sistema
- Registra la operación en logs
- Redirige a la carpeta padre

### Funciones Auxiliares

#### `get_safe_path(requested_path)`
Valida y normaliza rutas para prevenir path traversal

#### `get_file_icon(filename)`
Retorna el icono FontAwesome apropiado según la extensión

**Tipos soportados**:
- Documentos: PDF, Word, TXT
- Hojas de cálculo: Excel, CSV
- Imágenes: JPG, PNG, GIF, SVG, WebP
- Archivos comprimidos: ZIP, RAR, 7Z, TAR
- Código: Python, JavaScript, HTML, CSS, JSON

#### `format_file_size(size_bytes)`
Formatea el tamaño en formato legible (B, KB, MB, GB, TB)

## 🎯 URLs Configuradas

```python
# Explorador principal
/autenticacion/file-explorer/

# Navegación a subcarpetas
/autenticacion/file-explorer/<path:subpath>/

# Descarga de archivo
/autenticacion/file-download/<path:file_path>/

# Eliminación de archivo (POST)
/autenticacion/file-delete/<path:file_path>/
```

## 📱 Interfaz de Usuario

### Componentes de la UI

1. **Header**
   - Título y descripción del explorador
   - Botón "Volver" (cuando está en subcarpeta)

2. **Breadcrumb Navigation**
   - Muestra la ruta actual
   - Enlaces clicables para navegación rápida
   - Icono de home para directorio raíz

3. **Tabla de Archivos**
   - Columnas: Nombre, Tamaño, Modificado, Tipo, Acciones
   - Iconos diferenciados por tipo de archivo
   - Hover effects para mejor UX
   - Responsive design

4. **Acciones por Tipo**
   - **Carpetas**: Botón "Abrir" (azul)
   - **Archivos**: Botones "Descargar" (verde) y "Eliminar" (rojo)

5. **Modal de Confirmación**
   - Advertencia visual (ícono de peligro)
   - Mensaje claro sobre la acción irreversible
   - Muestra nombre del archivo a eliminar
   - Botones "Cancelar" y "Eliminar"

6. **Mensajes de Feedback**
   - Alertas de Bootstrap con auto-cierre (5 segundos)
   - Tipos: success, error, warning, info
   - Iconos contextuales

### Estados Especiales

**Carpeta Vacía**:
```
┌─────────────────────────┐
│    📂 Icono grande      │
│   "Carpeta vacía"       │
│  Texto descriptivo      │
│  [Botón Volver]         │
└─────────────────────────┘
```

## 🎨 Estilos CSS

### Variables CSS Personalizadas

```css
--explorer-primary: #007bff;
--explorer-danger: #dc3545;
--explorer-success: #28a745;
--explorer-warning: #ffc107;
--explorer-secondary: #6c757d;
```

### Características de Diseño

- Colores diferenciados por tipo de archivo
- Animaciones suaves al hacer hover
- Sombras y depth para jerarquía visual
- Responsive breakpoints (992px, 768px)
- Dark mode support (opcional)
- Print styles optimizados

## 📊 Casos de Uso

### Caso 1: Usuario Administrador Navega por Archivos

1. Usuario hace login como superusuario
2. Accede al menú "Explorador de Archivos"
3. Ve listado de carpetas en `/media/`
4. Hace clic en carpeta `email_attachments`
5. Ve archivos PDF dentro de la carpeta
6. Hace clic en "Descargar" para obtener un PDF
7. El archivo se descarga correctamente

### Caso 2: Usuario Administrador Elimina un Archivo

1. Usuario navega a la carpeta con el archivo
2. Hace clic en botón "Eliminar" del archivo
3. Aparece modal de confirmación
4. Lee advertencia sobre acción irreversible
5. Confirma haciendo clic en "Eliminar Archivo"
6. Archivo se elimina del sistema
7. Mensaje de éxito aparece
8. Usuario permanece en la carpeta actual

### Caso 3: Usuario Staff Intenta Acceder (Denegado)

1. Usuario staff autenticado intenta acceder
2. Sistema valida permisos
3. Usuario es redirigido al login
4. No tiene acceso al explorador

### Caso 4: Intento de Path Traversal (Bloqueado)

1. Atacante intenta URL: `/file-explorer/../../settings.py`
2. Sistema normaliza la ruta
3. Función `get_safe_path()` detecta ruta fuera de MEDIA_ROOT
4. Se lanza `PermissionDenied`
5. Mensaje de error mostrado
6. Operación bloqueada y registrada en logs

## 🧪 Pruebas Recomendadas

### Pruebas de Seguridad

- [ ] Verificar que usuarios no-superuser no pueden acceder
- [ ] Intentar path traversal: `../../etc/passwd`
- [ ] Intentar eliminar sin token CSRF
- [ ] Intentar acceder a archivos fuera de MEDIA_ROOT
- [ ] Verificar logs de operaciones críticas

### Pruebas Funcionales

- [ ] Navegar por múltiples niveles de carpetas
- [ ] Descargar diferentes tipos de archivos
- [ ] Eliminar archivo y verificar que se borra
- [ ] Breadcrumb navigation funciona correctamente
- [ ] Botón "Volver" retorna a carpeta padre
- [ ] Modal de confirmación aparece y funciona
- [ ] Mensajes de éxito/error se muestran

### Pruebas de UI

- [ ] Responsive en móvil (< 768px)
- [ ] Responsive en tablet (768px - 992px)
- [ ] Desktop estándar (> 992px)
- [ ] Iconos se muestran correctamente por tipo
- [ ] Hover effects funcionan
- [ ] Auto-cierre de alertas (5 segundos)

## 🚀 Despliegue y Configuración

### Requisitos Previos

- Django 5.1.7+
- Bootstrap 5
- FontAwesome 6
- Permisos de escritura en `/media/`

### Variables de Configuración

En `settings.py`:

```python
MEDIA_URL = '/media/'
MEDIA_ROOT = '/media'  # Producción
# o
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')  # Desarrollo
```

### Verificación Post-Instalación

1. Acceder a `/autenticacion/file-explorer/`
2. Verificar que aparece el explorador
3. Confirmar que se listan archivos correctamente
4. Probar descarga de un archivo
5. Verificar logs en consola/archivo

## 🔧 Mantenimiento

### Monitoreo

**Logs a revisar**:
- Descargas frecuentes de archivos sensibles
- Eliminaciones de archivos importantes
- Intentos de acceso denegado
- Errores de path traversal

**Métricas recomendadas**:
- Número de archivos en `/media/`
- Espacio utilizado en disco
- Frecuencia de eliminaciones
- Usuarios que acceden al explorador

### Limpieza Periódica

Considerar implementar:
- Script de limpieza de archivos antiguos
- Alertas de espacio en disco bajo
- Backup automático antes de eliminaciones críticas

## 📝 Mejoras Futuras

### Funcionalidades Posibles

- [ ] Subida de archivos
- [ ] Creación de carpetas
- [ ] Renombrar archivos/carpetas
- [ ] Mover archivos entre carpetas
- [ ] Vista previa de imágenes
- [ ] Vista previa de PDFs
- [ ] Búsqueda de archivos
- [ ] Filtrado por tipo de archivo
- [ ] Ordenamiento personalizado
- [ ] Selección múltiple para operaciones batch
- [ ] Compresión de archivos (ZIP)
- [ ] Estadísticas de uso de almacenamiento
- [ ] Historial de cambios
- [ ] Papelera de reciclaje (soft delete)

### Optimizaciones

- [ ] Paginación para carpetas grandes
- [ ] Caché de listados
- [ ] Lazy loading de imágenes
- [ ] WebSockets para actualizaciones en tiempo real
- [ ] Worker asíncrono para operaciones pesadas

## 📞 Soporte y Contacto

**Desarrollador**: Kilo Code AI  
**Fecha de Implementación**: 2025-11-09  
**Versión**: 1.0.0  
**Proyecto**: L&M Exotic Fruits - Sistema de Gestión

---

## 📄 Licencia

Este módulo es parte del sistema interno de L&M Exotic Fruits y está protegido por las políticas de la empresa.

## ⚠️ Advertencias

1. **Solo superusuarios**: Esta herramienta es poderosa. Dar acceso solo a usuarios confiables.
2. **Eliminación permanente**: Los archivos eliminados no se pueden recuperar.
3. **Archivos sensibles**: No almacenar información crítica sin encriptación.
4. **Backups**: Mantener backups regulares del directorio `/media/`.
5. **Espacio en disco**: Monitorear el espacio disponible regularmente.

---

**Última actualización**: 2025-11-09