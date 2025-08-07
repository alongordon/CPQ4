"""Models for the ``upload_STEP`` application."""

from django.core.validators import FileExtensionValidator
from django.db import models


class StepFile(models.Model):
    """Stores a user uploaded STEP file for later processing."""

    file = models.FileField(
        upload_to="step_files/",
        validators=[FileExtensionValidator(["step", "stp"])],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return self.file.name

