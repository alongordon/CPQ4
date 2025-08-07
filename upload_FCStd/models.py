from django.db import models


class FCStdUpload(models.Model):
    file = models.FileField(upload_to="fcstd/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "FCStd file"
        verbose_name_plural = "FCStd files"

    def __str__(self):
        return self.file.name
