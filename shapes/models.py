import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class ShapeAsset(models.Model):
    """Represents a shape asset in the library."""
    
    EDGE_CHOICES = [
        ('Top', 'Top'),
        ('Bottom', 'Bottom'),
        ('Left', 'Left'),
        ('Right', 'Right'),
    ]
    
    SHAPE_TYPE_CHOICES = [
        ('internal_cutout', 'Internal Cutout'),
        ('edge_affecting', 'Edge Affecting'),
    ]
    
    # Primary identifier
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic information
    name = models.CharField(max_length=200, help_text="Name of the shape")
    
    # File storage
    source_step = models.FileField(
        upload_to="shapes/step/",
        null=True,
        blank=True,
        help_text="Original STEP file upload (legacy)"
    )
    source_brep = models.FileField(
        upload_to="shapes/brep/",
        null=True,
        blank=True,
        help_text="Original BREP file upload"
    )
    canonical_brep = models.FileField(
        upload_to="shapes/brep/",
        null=True,
        blank=True,
        help_text="Planarized, XOY-aligned face in BREP format"
    )
    preview_svg = models.FileField(
        upload_to="shapes/preview/",
        null=True,
        blank=True,
        help_text="Quick thumbnail preview"
    )
    
    # Derived properties (read-only, computed from geometry)
    bbox_w_mm = models.FloatField(
        null=True,
        blank=True,
        help_text="Bounding box width in millimeters"
    )
    bbox_h_mm = models.FloatField(
        null=True,
        blank=True,
        help_text="Bounding box height in millimeters"
    )
    area_mm2 = models.FloatField(
        null=True,
        blank=True,
        help_text="Area in square millimeters"
    )
    has_holes = models.BooleanField(
        default=False,
        help_text="Whether the shape contains holes"
    )
    
    # Snap/placement defaults (admin-editable)
    default_edge = models.CharField(
        max_length=10,
        choices=EDGE_CHOICES,
        default='Left',
        help_text="Default edge for placement"
    )
    default_offset_mm = models.FloatField(
        default=0.0,
        help_text="Default offset from edge in millimeters"
    )
    
    # Attach frame parameters (defines local coordinate system)
    attach_x_mm = models.FloatField(
        default=0.0,
        help_text="X coordinate of attach point in shape's local frame"
    )
    attach_y_mm = models.FloatField(
        default=0.0,
        help_text="Y coordinate of attach point in shape's local frame"
    )
    attach_angle_deg = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(-360), MaxValueValidator(360)],
        help_text="Rotation angle in degrees for the attach frame"
    )
    
    # Panel2D library shape type
    shape_type = models.CharField(
        max_length=20,
        choices=SHAPE_TYPE_CHOICES,
        default='internal_cutout',
        help_text="Type of shape for Panel2D library integration"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Shape Asset"
        verbose_name_plural = "Shape Assets"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def is_processed(self):
        """Check if the shape has been processed (has canonical BREP)."""
        return bool(self.canonical_brep)
    
    @property
    def has_preview(self):
        """Check if the shape has a preview image."""
        return bool(self.preview_svg)
    
    def get_bbox_display(self):
        """Get formatted bounding box display."""
        if self.bbox_w_mm is not None and self.bbox_h_mm is not None:
            return f"{self.bbox_w_mm:.1f} × {self.bbox_h_mm:.1f} mm"
        return "Not computed"
    
    def get_area_display(self):
        """Get formatted area display."""
        if self.area_mm2 is not None:
            return f"{self.area_mm2:.1f} mm²"
        return "Not computed"
    
    def add_to_panel2d(self, panel, tx=0.0, ty=0.0, angle_deg=0.0, scale=1.0, edge=None, position=0.0):
        """Add this shape to a Panel2D instance with the specified transformation."""
        if not self.canonical_brep:
            raise ValueError(f"Shape {self.name} has no canonical BREP file")
        
        panel.add_library_shape(
            path=self.canonical_brep.path,
            kind=self.shape_type,
            tx=tx,
            ty=ty,
            angle_deg=angle_deg,
            scale=scale,
            edge=edge,
            position=position
        )
    
    def delete(self, *args, **kwargs):
        """Override delete to clean up associated files."""
        import os
        from django.conf import settings
        
        # Delete source files
        if self.source_brep:
            try:
                file_path = os.path.join(settings.MEDIA_ROOT, str(self.source_brep))
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted source BREP file: {file_path}")
            except Exception as e:
                print(f"Error deleting source BREP file: {e}")
        
        if self.source_step:
            try:
                file_path = os.path.join(settings.MEDIA_ROOT, str(self.source_step))
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted source STEP file: {file_path}")
            except Exception as e:
                print(f"Error deleting source STEP file: {e}")
        
        # Delete generated files
        if self.canonical_brep:
            try:
                file_path = os.path.join(settings.MEDIA_ROOT, str(self.canonical_brep))
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted canonical BREP file: {file_path}")
            except Exception as e:
                print(f"Error deleting canonical BREP file: {e}")
        
        if self.preview_svg:
            try:
                file_path = os.path.join(settings.MEDIA_ROOT, str(self.preview_svg))
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted preview SVG file: {file_path}")
            except Exception as e:
                print(f"Error deleting preview SVG file: {e}")
        
        # Call the parent delete method
        super().delete(*args, **kwargs)
