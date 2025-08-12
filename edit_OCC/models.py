from django.db import models

from upload_FCStd.models import FCStdUpload


class OccDocument(models.Model):
    """Represents an OCAF document generated from an FCStd file."""
    
    fcstd_file = models.ForeignKey(
        FCStdUpload, on_delete=models.CASCADE, related_name="occ_documents"
    )
    file = models.FileField(upload_to="occ_docs/")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "OCAF document"
        verbose_name_plural = "OCAF documents"
    
    def __str__(self) -> str:
        return self.file.name
