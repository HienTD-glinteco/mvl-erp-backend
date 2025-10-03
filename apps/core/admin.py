from django.contrib import admin

from .models import Permission, Role, User

admin.site.register(User)
admin.site.register(Permission)
admin.site.register(Role)
