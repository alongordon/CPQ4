from django.contrib import admin

from .models import FCStdUpload


@admin.register(FCStdUpload)
class FCStdUploadAdmin(admin.ModelAdmin):
    list_display = ("file", "uploaded_at")
