from dataclasses import dataclass, field
from typing import List, Tuple
import math

from OCC.Core.gp import gp_Pnt, gp_Ax1, gp_Dir, gp_Trsf, gp_Vec, gp_Pln, gp_Ax3
from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Face, TopoDS_Wire
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepTools import breptools
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_Transform, BRepBuilderAPI_MakeFace
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Core.ShapeFix import ShapeFix_Face
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib


@dataclass
class Panel2D:
    """Planar panel as a single face. Library BREP profiles are cut from this face."""
    width: float
    height: float
    origin: Tuple[float, float] = (0.0, 0.0)

    # store transformed cut faces to apply during build
    _edge_cuts: List[TopoDS_Shape] = field(default_factory=list, init=False, repr=False)
    _inner_wires: List[TopoDS_Wire] = field(default_factory=list, init=False, repr=False)

    # ---------- public API ----------
    def add_library_shape(
        self,
        path: str,
        kind: str,                # "edge_affecting" | "internal_cutout"
        tx: float = 0.0,
        ty: float = 0.0,
        angle_deg: float = 0.0,   # rotation about Z (degrees)
        scale: float = 1.0        # uniform scale about origin
    ) -> None:
        """Load a BREP profile, place it, and schedule it as a cut against the panel."""
        print(f"Adding shape from {path}, kind: {kind}, pos: ({tx}, {ty}), angle: {angle_deg}")
        shape = self._load_brep(path)
        print(f"Loaded BREP shape: {shape}")
        
        # Get shape bounds
        bbox = Bnd_Box()
        brepbndlib.Add(shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        print(f"Original shape bounds: X({xmin:.1f}, {xmax:.1f}), Y({ymin:.1f}, {ymax:.1f}), Z({zmin:.1f}, {zmax:.1f})")
        
        wire = self._profile_wire_from_shape(shape)
        print(f"Extracted wire: {wire}")
        
        if kind == "internal_cutout":
            # For internal cutouts: convert relative coordinates to absolute
            # tx = distance from left edge, ty = distance from top edge
            shape_x = self.origin[0] + tx  # left edge + offset
            shape_y = self.origin[1] + self.height - ty  # top edge - offset (Y is inverted)
            
            # Transform the wire
            transformed_shape = BRepBuilderAPI_Transform(wire, 
                               self._make_trsf(shape_x, shape_y, angle_deg, scale), True).Shape()
            print(f"Transformed internal shape: {transformed_shape}")
            
            # Extract wire from transformed shape
            exp = TopExp_Explorer(transformed_shape, TopAbs_WIRE)
            if exp.More():
                placed_wire = exp.Current()
                print(f"Extracted internal wire: {placed_wire}")
                
                # Validate the wire before adding (simplified)
                try:
                    # Test if we can create a face from this wire (validation)
                    test_face = BRepBuilderAPI_MakeFace(placed_wire).Face()
                    if not BRepCheck_Analyzer(test_face, True).IsValid():
                        print(f"Warning: Invalid internal wire, skipping")
                        return
                except Exception as e:
                    print(f"Warning: Could not validate internal wire: {e}")
                    return
                
                self._inner_wires.append(placed_wire)
                print(f"Added as internal wire. Total internal wires: {len(self._inner_wires)}")
            else:
                print("Error: No wire found in transformed shape")
        else:
            # For edge-affecting shapes: the frontend already calculates the correct position
            # based on the selected edge (Left, Right, Top, Bottom) and provides
            # coordinates that should place the shape correctly to cut the panel edge
            
            # Get the shape's bounding box for debugging
            bbox_shape = Bnd_Box()
            brepbndlib.Add(shape, bbox_shape)
            sxmin, symin, szmin, sxmax, symax, szmax = bbox_shape.Get()
            shape_width = sxmax - sxmin
            shape_height = symax - symin
            
            print(f"Shape dimensions: {shape_width:.1f} x {shape_height:.1f}")
            print(f"Frontend provided position: ({tx}, {ty})")
            
            print(f"=== EDGE AFFECTING SHAPE DEBUG ===")
            print(f"Panel dimensions: width={self.width}, height={self.height}")
            print(f"Panel origin: {self.origin}")
            print(f"Final position: tx={tx}, ty={ty}")
            print(f"Angle: {angle_deg} degrees, Scale: {scale}")
            
            # Get original wire bounds for comparison
            bbox_wire = Bnd_Box()
            brepbndlib.Add(wire, bbox_wire)
            xmin_w, ymin_w, zmin_w, xmax_w, ymax_w, zmax_w = bbox_wire.Get()
            print(f"Original wire bounds: X({xmin_w:.1f}, {xmax_w:.1f}), Y({ymin_w:.1f}, {ymax_w:.1f})")
            
            # First rotate the wire around its own center (if needed)
            if abs(angle_deg) > 1e-12:
                print(f"DEBUG: Applying rotation of {angle_deg}° to wire")
                wire = self._rotate_wire_around_center(wire, angle_deg)
                
                # DEBUG: Check wire bounds after rotation
                bbox_rotated_wire = Bnd_Box()
                brepbndlib.Add(wire, bbox_rotated_wire)
                rxmin, rymin, rzmin, rxmax, rymax, rzmax = bbox_rotated_wire.Get()
                print(f"DEBUG: Wire bounds after rotation: X({rxmin:.1f}, {rxmax:.1f}), Y({rymin:.1f}, {rymax:.1f})")
                
                # Normalize rotated wire to start at (0,0) if it has negative coordinates
                if rxmin < 0 or rymin < 0:
                    normalize_x = -rxmin if rxmin < 0 else 0
                    normalize_y = -rymin if rymin < 0 else 0
                    print(f"DEBUG: Normalizing wire by translating ({normalize_x:.1f}, {normalize_y:.1f})")
                    
                    # Create normalization transformation
                    norm_tr = gp_Trsf()
                    norm_tr.SetTranslation(gp_Vec(normalize_x, normalize_y, 0))
                    wire = BRepBuilderAPI_Transform(wire, norm_tr, True).Shape()
                    
                    # Check normalized bounds
                    bbox_normalized = Bnd_Box()
                    brepbndlib.Add(wire, bbox_normalized)
                    nxmin, nymin, nzmin, nxmax, nymax, nzmax = bbox_normalized.Get()
                    print(f"DEBUG: Wire bounds after normalization: X({nxmin:.1f}, {nxmax:.1f}), Y({nymin:.1f}, {nymax:.1f})")
            
            # Create edge shape face from the rotated wire
            edge_shape_face_maker = BRepBuilderAPI_MakeFace(wire)
            edge_shape_face = edge_shape_face_maker.Face()
            print(f"Created edge shape face from rotated wire: {edge_shape_face}")
            
            # Then translate edge shape face to target position
            transformed_edge_shape_face = self._translate_shape(edge_shape_face, tx, ty)
            print(f"Transformed edge shape face: {transformed_edge_shape_face}")
            
            # Get transformed edge shape face bounds
            bbox_transformed_edge = Bnd_Box()
            brepbndlib.Add(transformed_edge_shape_face, bbox_transformed_edge)
            xmin_e, ymin_e, zmin_e, xmax_e, ymax_e, zmax_e = bbox_transformed_edge.Get()
            print(f"Transformed edge shape face bounds: X({xmin_e:.1f}, {xmax_e:.1f}), Y({ymin_e:.1f}, {ymax_e:.1f}), Z({zmin_e:.1f}, {zmax_e:.1f})")
            
            # Check if edge shape face intersects with panel face
            panel_face = self._base_rect_face()
            panel_bbox = Bnd_Box()
            brepbndlib.Add(panel_face, panel_bbox)
            pxmin, pymin, pzmin, pxmax, pymax, pzmax = panel_bbox.Get()
            print(f"Panel face bounds: X({pxmin:.1f}, {pxmax:.1f}), Y({pymin:.1f}, {pymax:.1f})")
            
            # Check for intersection between edge shape face and panel face
            if (xmax_e < pxmin or xmin_e > pxmax or ymax_e < pymin or ymin_e > pymax):
                print(f"WARNING: Edge shape face does not intersect with panel face!")
                print(f"Edge shape face is outside panel face bounds")
            else:
                print(f"Edge shape face intersects with panel face ✓")
            
            # Validate the edge shape face before adding
            if not BRepCheck_Analyzer(transformed_edge_shape_face, True).IsValid():
                print(f"Warning: Invalid edge shape face, skipping")
                return
                
            self._edge_cuts.append(transformed_edge_shape_face)
            print(f"Added as edge cut. Total edge cuts: {len(self._edge_cuts)}")
            print(f"Edge cut shape type: {transformed_edge_shape_face.ShapeType()}")
            print(f"Edge cut bounds: X({xmin_e:.1f}, {xmax_e:.1f}), Y({ymin_e:.1f}, {ymax_e:.1f})")
            print(f"=== END EDGE AFFECTING DEBUG ===")

    def clear_library_shapes(self) -> None:
        """Clear all library shapes from the panel."""
        self._edge_cuts.clear()
        self._inner_wires.clear()

    def build_face(self) -> TopoDS_Shape:
        """Build the base rectangular face of the panel."""
        return self._base_rect_face()

    def _outer_wire_after_edge_cuts(self) -> TopoDS_Wire:
        """Get the updated outer wire after applying edge cuts."""
        # Start from the base rectangular face
        current_face = self._base_rect_face()
        print(f"Starting with base face: {current_face}")
        
        # Apply each edge cut as a face cut; take the largest face each time
        for i, cut_face in enumerate(self._edge_cuts):
            print(f"Applying edge cut {i+1} to get updated outer wire")
            print(f"Cut face: {cut_face}")
            
            # Perform boolean cut
            cut_op = BRepAlgoAPI_Cut(current_face, cut_face)
            cut_op.Build()
            
            if not cut_op.IsDone():
                print(f"Warning: Boolean cut {i+1} failed")
                continue
                
            cut_result = cut_op.Shape()
            print(f"Cut result: {cut_result}")
            
            # Extract the largest face from the result
            current_face = self._largest_face(cut_result)
            print(f"Largest face after cut {i+1}: {current_face}")
        
        # Extract wires from the current face and pick the outer boundary
        wires = []
        wexp = TopExp_Explorer(current_face, TopAbs_WIRE)
        while wexp.More():
            wire = wexp.Current()
            wires.append(wire)
            print(f"Found wire: {wire}")
            wexp.Next()
        
        print(f"Total wires found: {len(wires)}")
        
        if not wires:
            # Fallback to original outer wire if no wires found
            print("No wires found after edge cuts, using original outer wire")
            return self._make_outer_rect_wire()
        
        outer_wire = self._largest_wire_by_area_proxy(wires)
        print(f"Selected outer wire: {outer_wire}")
        return outer_wire

    def as_shape(self) -> TopoDS_Shape:
        """Build final planar face after applying edge and internal cuts."""
        print(f"Building panel with {len(self._edge_cuts)} edge cuts and {len(self._inner_wires)} internal wires")
        
        # If no edge cuts, just return the base face with holes
        if len(self._edge_cuts) == 0:
            print("No edge cuts, returning base face with holes")
            maker = BRepBuilderAPI_MakeFace(self._make_outer_rect_wire())
            
            for i, w in enumerate(self._inner_wires):
                print(f"Adding internal wire {i+1}: {w}")
                try:
                    maker.Add(w)  # inner loops = holes
                    print(f"Successfully added internal wire {i+1}")
                except Exception as e:
                    print(f"Error adding internal wire {i+1}: {e}")
                    # Continue with other wires instead of failing completely
            
            try:
                face = maker.Face()
                print(f"Created face with {len(self._inner_wires)} internal wires")
                
                # Simple validation - if it fails, fall back to face without holes
                try:
                    self._validate(face)
                    print("Face validation passed")
                    return face
                except Exception as validation_error:
                    print(f"Face validation failed: {validation_error}")
                    print("Falling back to face without internal wires")
                    fallback_maker = BRepBuilderAPI_MakeFace(self._make_outer_rect_wire())
                    fallback_face = fallback_maker.Face()
                    self._validate(fallback_face)
                    return fallback_face
                    
            except Exception as e:
                print(f"Error creating face with internal wires: {e}")
                # Fallback to face without internal wires
                print("Falling back to face without internal wires")
                fallback_maker = BRepBuilderAPI_MakeFace(self._make_outer_rect_wire())
                fallback_face = fallback_maker.Face()
                self._validate(fallback_face)
                return fallback_face
        
        # 1) Compute the final outer boundary that already includes notches/slots
        outer_wire = self._outer_wire_after_edge_cuts()
        print(f"Final outer wire: {outer_wire}")
        
        # 2) Build a face from that boundary and add inner wires (holes) directly
        maker = BRepBuilderAPI_MakeFace(outer_wire)
        
        for i, w in enumerate(self._inner_wires):
            print(f"Adding internal wire {i+1}: {w}")
            try:
                maker.Add(w)  # inner loops = holes
                print(f"Successfully added internal wire {i+1}")
            except Exception as e:
                print(f"Error adding internal wire {i+1}: {e}")
                # Continue with other wires instead of failing completely
        
        try:
            face = maker.Face()
            print(f"Final face with holes: {face}")
            
            # Simple validation - if it fails, fall back to face without holes
            try:
                self._validate(face)
                print("Face validation passed")
            except Exception as validation_error:
                print(f"Face validation failed: {validation_error}")
                print("Falling back to face without internal wires")
                fallback_maker = BRepBuilderAPI_MakeFace(outer_wire)
                face = fallback_maker.Face()
                print(f"Fallback face: {face}")
                    
        except Exception as e:
            print(f"Error creating face with internal wires: {e}")
            # Fallback to face without internal wires
            print("Falling back to face without internal wires")
            fallback_maker = BRepBuilderAPI_MakeFace(outer_wire)
            face = fallback_maker.Face()
            print(f"Fallback face: {face}")
        
        # 3) Optional: fix orientations
        try:
            fix = ShapeFix_Face(face)
            fix.Perform()
            face = fix.Face()
            print("Applied ShapeFix_Face")
        except Exception as e:
            print(f"ShapeFix_Face failed: {e}")
        
        # 4) Validate and return
        self._validate(face)
        print(f"Final panel shape: {face}")
        
        # Debug: Print wire information
        print(f"=== FINAL PANEL DEBUG ===")
        wires = []
        wexp = TopExp_Explorer(face, TopAbs_WIRE)
        while wexp.More():
            wire = wexp.Current()
            wires.append(wire)
            wexp.Next()
        
        print(f"Total wires in final face: {len(wires)}")
        for i, wire in enumerate(wires):
            bbox = Bnd_Box()
            brepbndlib.Add(wire, bbox)
            xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
            print(f"Wire {i+1} bounds: X({xmin:.1f}, {xmax:.1f}), Y({ymin:.1f}, {ymax:.1f})")
        print(f"=== END FINAL PANEL DEBUG ===")
        
        return face

    def get_dimensions(self) -> tuple:
        """Get the panel dimensions."""
        return (self.width, self.height)

    def get_library_shapes_count(self) -> tuple:
        """Get count of library shapes by type."""
        return (len(self._edge_cuts), len(self._inner_wires))

    def view(self) -> None:
        """Quick native OCC viewer to inspect the result."""
        try:
            from OCC.Display.SimpleGui import init_display
            shape = self.as_shape()
            display, start_display, *_ = init_display()
            display.DisplayShape(shape, update=True)
            display.FitAll()
            start_display()
        except ImportError:
            print("OCC Display not available for interactive viewing")

    def __str__(self) -> str:
        """String representation of the panel."""
        edge_count, inner_count = self.get_library_shapes_count()
        return f"Panel2D({self.width}mm x {self.height}mm) with {edge_count} edge cuts, {inner_count} internal wires"

    # ---------- helpers ----------
    def _make_outer_rect_wire(self) -> TopoDS_Wire:
        """Create the outer rectangular wire."""
        ox, oy = self.origin
        w, h = self.width, self.height
        poly = BRepBuilderAPI_MakePolygon()
        poly.Add(gp_Pnt(ox,   oy,   0))
        poly.Add(gp_Pnt(ox+w, oy,   0))
        poly.Add(gp_Pnt(ox+w, oy+h, 0))
        poly.Add(gp_Pnt(ox,   oy+h, 0))
        poly.Close()
        return poly.Wire()

    def _base_rect_face(self) -> TopoDS_Face:
        """Create the base rectangular face."""
        return BRepBuilderAPI_MakeFace(self._make_outer_rect_wire()).Face()

    def _rotate_wire_around_center(self, wire, angle_deg: float):
        """Rotate a wire around its bottom-left corner to maintain (0,0) origin."""
        if abs(angle_deg) < 1e-12:
            return wire
            
        # Calculate wire bounds to get bottom-left corner
        bbox = Bnd_Box()
        brepbndlib.Add(wire, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        
        # Use bottom-left corner as rotation point to maintain (0,0) origin
        rotation_x = xmin
        rotation_y = ymin
        
        # Convert degrees to radians
        ang = math.radians(angle_deg)
        print(f"DEBUG: Rotating wire around bottom-left corner ({rotation_x:.1f}, {rotation_y:.1f})")
        print(f"DEBUG: Angle: {angle_deg}° = {ang:.4f} radians")
        
        # Create rotation transformation around bottom-left corner
        tr = gp_Trsf()
        tr.SetRotation(gp_Ax1(gp_Pnt(rotation_x, rotation_y, 0), gp_Dir(0, 0, 1)), ang)
        
        # Apply rotation
        rotated_wire = BRepBuilderAPI_Transform(wire, tr, True).Shape()
        return rotated_wire

    def _rotate_shape_around_center(self, shape, angle_deg: float):
        """Rotate a shape around its own center."""
        if abs(angle_deg) < 1e-12:
            return shape
            
        # Calculate shape center
        bbox = Bnd_Box()
        brepbndlib.Add(shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        center_x = (xmin + xmax) / 2
        center_y = (ymin + ymax) / 2
        
        # Convert degrees to radians
        ang = math.radians(angle_deg)
        print(f"DEBUG: Rotating shape around center ({center_x:.1f}, {center_y:.1f})")
        print(f"DEBUG: Angle: {angle_deg}° = {ang:.4f} radians")
        
        # Create rotation transformation around shape center
        tr = gp_Trsf()
        tr.SetRotation(gp_Ax1(gp_Pnt(center_x, center_y, 0), gp_Dir(0, 0, 1)), ang)
        
        # Apply rotation
        rotated_shape = BRepBuilderAPI_Transform(shape, tr, True).Shape()
        return rotated_shape

    def _make_trsf(self, tx: float, ty: float, angle_deg: float, scale: float) -> gp_Trsf:
        """Create transformation matrix for translation only."""
        tr = gp_Trsf()
        # Only handle translation - rotation is done separately
        if abs(tx) > 1e-12 or abs(ty) > 1e-12:
            t = gp_Trsf()
            t.SetTranslation(gp_Vec(tx, ty, 0))
            tr = tr.Multiplied(t)
        return tr

    def _translate_shape(self, shape, tx: float, ty: float):
        """Translate a shape to the target position."""
        if abs(tx) < 1e-12 and abs(ty) < 1e-12:
            return shape
            
        print(f"DEBUG: Translating shape to ({tx}, {ty})")
        
        # Create translation transformation
        tr = gp_Trsf()
        tr.SetTranslation(gp_Vec(tx, ty, 0))
        
        # Apply translation
        translated_shape = BRepBuilderAPI_Transform(shape, tr, True).Shape()
        return translated_shape

    def _load_brep(self, path: str) -> TopoDS_Shape:
        """Load a BREP file from the given path."""
        builder = BRep_Builder()
        shape = TopoDS_Shape()
        if not breptools.Read(shape, path, builder):
            # breptools.Read returns None on success in some builds; we check validity next
            pass
        return shape

    def _profile_wire_from_shape(self, shp: TopoDS_Shape) -> TopoDS_Wire:
        """Extract a usable wire (outer boundary) from an input 2D BREP profile."""
        # If it's already a wire, return it
        exp = TopExp_Explorer(shp, TopAbs_WIRE)
        if exp.More():
            return exp.Current()

        # If it's (or contains) a face, pick the biggest outer wire from faces
        f = self._largest_face(shp)
        # Use the face boundary as a wire
        # BRepTools.OuterWire is available, but picking the largest wire works well for simple profiles.
        wires = []
        expw = TopExp_Explorer(f, TopAbs_WIRE)
        while expw.More():
            wires.append(expw.Current())
            expw.Next()
        if not wires:
            raise ValueError("No wire found in library shape")
        # Choose the longest-perimeter wire as "outer"
        return self._largest_wire_by_area_proxy(wires)

    def _largest_face(self, shp: TopoDS_Shape) -> TopoDS_Face:
        """From any shape, return the planar face with the largest area."""
        best_face = None
        best_area = -1.0
        exp = TopExp_Explorer(shp, TopAbs_FACE)
        while exp.More():
            face = exp.Current()
            props = GProp_GProps()
            brepgprop.SurfaceProperties(face, props)
            area = props.Mass()
            if area > best_area:
                best_area = area
                best_face = face
            exp.Next()
        if best_face is None:
            raise ValueError("No face found after boolean; input may not be planar/closed")
        return best_face

    def _largest_wire_by_area_proxy(self, wires: List[TopoDS_Wire]) -> TopoDS_Wire:
        """Heuristic: build a temporary face from each wire and take the largest area."""
        best_wire = None
        best_area = -1.0
        for w in wires:
            try:
                f = BRepBuilderAPI_MakeFace(w).Face()
                props = GProp_GProps()
                brepgprop.SurfaceProperties(f, props)
                area = props.Mass()
                if area > best_area:
                    best_area = area
                    best_wire = w
            except Exception:
                continue
        if best_wire is None:
            raise ValueError("Could not evaluate any wire for area")
        return best_wire



    def _validate(self, shape: TopoDS_Shape) -> None:
        """Validate that the resulting shape is a valid BREP."""
        if not BRepCheck_Analyzer(shape, True).IsValid():
            raise ValueError("Resulting panel face is not a valid BREP")

    def save_brep(self, path: str) -> None:
        """Save the panel as a BREP file.
        
        Parameters
        ----------
        path: str
            Path where to save the BREP file
            
        Raises
        ------
        RuntimeError
            If the BREP file cannot be written
        """
        try:
            from OCC.Core.BRepTools import breptools_Write
            
            # Get the final panel shape with all cuts
            shape = self.as_shape()
            
            # Validate the shape before saving
            self._validate(shape)
            
            # Write the BREP file
            if not breptools_Write(shape, path):
                raise RuntimeError(f"Failed to write BREP file: {path}")
                
            print(f"Panel saved to BREP file: {path}")
            
        except Exception as e:
            raise RuntimeError(f"Error saving panel to BREP: {e}")
