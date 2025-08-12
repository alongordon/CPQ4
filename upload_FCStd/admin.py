from django.contrib import admin, messages

from .models import FCStdUpload
from edit_OCC.services import create_ocaf_from_fcstd


@admin.register(FCStdUpload)
class FCStdUploadAdmin(admin.ModelAdmin):
    list_display = ("file", "uploaded_at")
    change_list_template = "admin/upload_FCStd/fcstdupload/change_list.html"
    actions = ["generate_ocaf_action"]

    @admin.action(description="Generate OCAF document")
    def generate_ocaf_action(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request, "Please select exactly one FCStd file.", level=messages.ERROR
            )
            return
        fcstd_file = queryset.first()
        try:
            create_ocaf_from_fcstd(fcstd_file)
            self.message_user(request, "OCAF document created successfully.")
        except Exception as e:
            self.message_user(
                request, f"Error creating OCAF document: {e}", level=messages.ERROR
            )
