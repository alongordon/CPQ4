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
    
    def _wire_from_shape_relaxed(self, shape):
        """
        Extract a usable closed wire from a shape, handling various topology structures.
        This is more robust than simple wire extraction for shapes from different CAD systems.
        """
        from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_WIRE
        from OCC.Core.TopoDS import topods_Face, topods_Wire, topods_Edge
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
        from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
        from OCC.Core.BRepCheck import BRepCheck_Analyzer
        
        print(f"  Wire extraction: Input shape type: {type(shape)}")
        
        # 1) try wires directly
        print("  Wire extraction: Step 1 - Looking for wires directly...")
        expw = TopExp_Explorer(shape, TopAbs_WIRE)
        if expw.More():
            wire = topods_Wire(expw.Current())
            print(f"  Wire extraction: Found wire directly, type: {type(wire)}")
            return wire

        # 2) try face outer boundary
        print("  Wire extraction: Step 2 - Looking for faces...")
        expf = TopExp_Explorer(shape, TopAbs_FACE)
        if expf.More():
            f = topods_Face(expf.Current())
            print(f"  Wire extraction: Found face, type: {type(f)}")
            # Rebuild the outer wire via MakeFace->Wire extraction (avoids version diffs)
            tmp = BRepBuilderAPI_MakeFace(f).Face()
            wexp = TopExp_Explorer(tmp, TopAbs_WIRE)
            if wexp.More():
                wire = topods_Wire(wexp.Current())
                print(f"  Wire extraction: Extracted wire from face, type: {type(wire)}")
                return wire

        # 3) single periodic edge -> make a face then re-extract wire
        print("  Wire extraction: Step 3 - Looking for edges...")
        edges = []
        expe = TopExp_Explorer(shape, TopAbs_EDGE)
        while expe.More():
            edges.append(topods_Edge(expe.Current()))
            expe.Next()
        print(f"  Wire extraction: Found {len(edges)} edges")
        
        if len(edges) == 1:
            print("  Wire extraction: Single edge found, checking if periodic...")
            ba = BRepAdaptor_Curve(edges[0])
            is_periodic = ba.IsPeriodic()
            print(f"  Wire extraction: Edge is periodic: {is_periodic}")
            
            if is_periodic:
                # either wrap edge in a wire...
                w = BRepBuilderAPI_MakeWire(edges[0]).Wire()
                print(f"  Wire extraction: Created wire from periodic edge, type: {type(w)}")
                # ...or more robust: make a planar face and re-extract boundary
                ftry = BRepBuilderAPI_MakeFace(w).Face()
                face_valid = BRepCheck_Analyzer(ftry, True).IsValid()
                print(f"  Wire extraction: Face from periodic edge valid: {face_valid}")
                
                if face_valid:
                    wexp = TopExp_Explorer(ftry, TopAbs_WIRE)
                    if wexp.More():
                        wire = topods_Wire(wexp.Current())
                        print(f"  Wire extraction: Extracted wire from periodic edge face, type: {type(wire)}")
                        return wire
                return w  # fallback

        print("  Wire extraction: No usable closed boundary found")
        raise ValueError("No usable closed boundary found")

    def canonicalize_wire_orientation(self, brep_path):
        """
        Canonicalize the wire orientation to CCW/FORWARD (orientation 0) and validate closure.
        This ensures all shapes are stored in a consistent format and are properly closed.
        """
        try:
            from OCC.Core.BRep import BRep_Builder
            from OCC.Core.BRepTools import breptools, breptools_Write
            from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Wire
            from OCC.Core.TopAbs import TopAbs_WIRE
            from OCC.Core.TopExp import TopExp_Explorer
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
            from OCC.Core.BRepCheck import BRepCheck_Analyzer, BRepCheck_Wire, BRepCheck_NoError
            
            print(f"=== WIRE VALIDATION DEBUG ===")
            print(f"Processing BREP file: {brep_path}")
            
            # Load the BREP file
            builder = BRep_Builder()
            shape = TopoDS_Shape()
            read_result = breptools.Read(shape, brep_path, builder)
            print(f"BREP read result: {read_result}")
            
            # In some PythonOCC versions, breptools.Read returns None on success
            if read_result is False:  # Explicitly check for False
                raise ValueError(f"Could not read BREP file: {brep_path}")
            
            # Check if we got a valid shape
            if shape.IsNull():
                raise ValueError(f"No valid shape found in BREP file: {brep_path}")
            
            print(f"Shape loaded successfully, type: {type(shape)}")
            
            # Extract the wire using robust method
            print("Extracting wire using robust method...")
            wire = self._wire_from_shape_relaxed(shape)
            print(f"Wire extracted successfully, type: {type(wire)}")
            print(f"Original wire orientation: {wire.Orientation()}")
            
            # Validate wire closure using proper enum comparison
            print("Checking wire closure status...")
            wire_checker = BRepCheck_Wire(wire)
            st = wire_checker.Status()
            print(f"Wire status: {st}")
            print(f"BRepCheck_NoError value: {BRepCheck_NoError}")
            print(f"Status comparison: {st} != {BRepCheck_NoError} = {st != BRepCheck_NoError}")
            
            if st != BRepCheck_NoError:
                print(f"Wire closure check failed with status: {st}")
                # As a last check, try making a face on Z=0 and validate that
                print("Attempting face creation as fallback validation...")
                face_try = BRepBuilderAPI_MakeFace(wire).Face()
                face_valid = BRepCheck_Analyzer(face_try, True).IsValid()
                print(f"Face creation result: {face_valid}")
                
                if not face_valid:
                    raise ValueError(f"Wire not closed (status={st}) and face build failed. Internal shapes must be properly closed.")
                else:
                    print(f"Wire closure validation passed via face validation ✓")
            else:
                print(f"Wire closure validation passed ✓")
            
            print(f"=== END WIRE VALIDATION DEBUG ===")
            
            # Check if wire needs to be canonicalized (should be FORWARD = 0)
            if wire.Orientation() != 0:  # Not FORWARD
                print(f"Canonicalizing wire orientation from {wire.Orientation()} to FORWARD (0)")
                
                # Reverse the wire to make it FORWARD
                wire.Reverse()
                print(f"Wire orientation after canonicalization: {wire.Orientation()}")
                
                # Create a new face from the canonicalized wire
                face_maker = BRepBuilderAPI_MakeFace(wire)
                if not face_maker.IsDone():
                    raise ValueError("Could not create face from canonicalized wire")
                
                canonical_face = face_maker.Face()
                
                # Validate the canonicalized face
                if not BRepCheck_Analyzer(canonical_face, True).IsValid():
                    raise ValueError("Canonicalized face is not valid")
                
                # Write the canonicalized shape back to the file
                if not breptools_Write(canonical_face, brep_path):
                    raise ValueError(f"Could not write canonicalized BREP file: {brep_path}")
                
                print(f"Successfully canonicalized wire orientation in: {brep_path}")
                return True
            else:
                print(f"Wire already has canonical orientation (FORWARD = 0)")
                return True
                
        except Exception as e:
            print(f"Error canonicalizing wire orientation: {e}")
            return False
    
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
