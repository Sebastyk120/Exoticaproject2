from django.contrib.auth.models import User, Group
from import_export import resources


class UserResource(resources.ModelResource):
    class Meta:
        model = User


class GroupResource(resources.ModelResource):
    class Meta:
        model = Group