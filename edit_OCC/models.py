"""Models for the ``edit_OCC`` application."""

from django.db import models

from upload_STEP.models import StepFile


class OccDocument(models.Model):
    """Represents an exported OCAF document generated from a STEP file."""

    step_file = models.ForeignKey(
        StepFile, on_delete=models.CASCADE, related_name="occ_documents"
    )
    file = models.FileField(upload_to="occ_docs/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return self.file.name

