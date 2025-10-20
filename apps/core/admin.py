from django.contrib import admin

from .models import AdministrativeUnit, PasswordResetOTP, Permission, Province, Role, User, UserDevice

admin.site.register(User)
admin.site.register(Permission)
admin.site.register(Role)
admin.site.register(PasswordResetOTP)
admin.site.register(UserDevice)
admin.site.register(Province)
admin.site.register(AdministrativeUnit)
