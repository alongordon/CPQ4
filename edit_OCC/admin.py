from django.contrib import admin

from .models import OccDocument


@admin.register(OccDocument)
class OccDocumentAdmin(admin.ModelAdmin):
    """Admin representation of :class:`~edit_OCC.models.OccDocument`."""
    
    list_display = ("id", "fcstd_file", "file", "created_at")
