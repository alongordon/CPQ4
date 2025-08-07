"""Admin interface configuration for the ``upload_STEP`` app."""

from django.contrib import admin, messages

from edit_OCC.services import create_occ_document
from .models import StepFile


@admin.register(StepFile)
class StepFileAdmin(admin.ModelAdmin):
    """Admin representation of :class:`~upload_STEP.models.StepFile`."""

    list_display = ("id", "file", "uploaded_at")
    change_list_template = "admin/upload_STEP/stepfile/change_list.html"
    actions = ["build_occ_document_action"]

    @admin.action(description="Build OCC document")
    def build_occ_document_action(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request, "Please select exactly one STEP file.", level=messages.ERROR
            )
            return
        step_file = queryset.first()
        create_occ_document(step_file)
        self.message_user(request, "OCC document created successfully.")

