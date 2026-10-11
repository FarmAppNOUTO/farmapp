from django.contrib import admin

# Register your models here.

from .models import Field, FieldRecord, SelectOption
admin.site.register(Field)
admin.site.register(FieldRecord)
admin.site.register(SelectOption)