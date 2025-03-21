from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import User, Group
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from autenticacion.resources import UserResource, GroupResource


# Register your models here.

# Registramos el modelo LogEntry en el admin
@admin.register(LogEntry)
class LogEntryAdmin(ModelAdmin):
    list_display = ('action_time', 'user', 'content_type', 'object_repr', 'action_flag')
    list_filter = ('action_time', 'user', 'content_type')
    search_fields = ('object_repr', 'change_message')
    date_hierarchy = 'action_time'
    readonly_fields = ('action_time', 'user', 'content_type', 'object_id', 'object_repr', 'action_flag', 'change_message')

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

# Desregistrar los modelos User y Group de manera segura
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass

# Registramos el modelo User con Unfold
@admin.register(User)
class UserAdmin(ModelAdmin, ImportExportModelAdmin, BaseUserAdmin):
    import_error_display = ("message", "row", "traceback")
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = UserResource
    # Formularios de Unfold
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


# Registrar de nuevo el modelo Group con la clase personalizada
@admin.register(Group)
class GroupAdmin(ModelAdmin, ImportExportModelAdmin, BaseGroupAdmin):
    import_error_display = ("message", "row", "traceback")
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = GroupResource