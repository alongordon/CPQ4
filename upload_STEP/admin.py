"""Admin interface configuration for the ``upload_STEP`` app."""

from django.contrib import admin

from .models import StepFile


@admin.register(StepFile)
class StepFileAdmin(admin.ModelAdmin):
    """Admin representation of :class:`~upload_STEP.models.StepFile`."""

    list_display = ("id", "file", "uploaded_at")

