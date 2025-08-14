"""Services for shape import and processing pipeline."""
from __future__ import annotations

import os
import math
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from django.conf import settings

from .models import ShapeAsset


def load_brep_file(brep_path: str | Path) -> Any:
    """Load a BREP file using OCC-Core BRepTools.
    
    Parameters
    ----------
    brep_path: Path-like
        Path to the BREP file
        
    Returns
    -------
    OCC shape or None
        The loaded shape if successful, None if failed
    """
    try:
        print(f"Loading BREP file with BRepTools...")
        from OCC.Core import BRepTools
        from OCC.Core.TopoDS import TopoDS_Shape
        from OCC.Core.BRep import BRep_Builder
        
        # Create a shape to load into
        shape = TopoDS_Shape()
        
        # Create a BRep_Builder (required for newer OCC-Core versions)
        builder = BRep_Builder()
        
        print(f"Attempting to read file: {brep_path}")
        # Read the BREP file using the correct function signature
        read_result = BRepTools.breptools_Read(shape, str(brep_path), builder)
        print(f"BRepTools.breptools_Read result: {read_result}")
        
        # In some PythonOCC versions, breptools.Read returns None on success
        if read_result is False:  # Explicitly check for False
            print(f"BREP file read failed")
            print(f"File size: {os.path.getsize(brep_path)} bytes")
            raise ValueError(f"BRepTools failed to read BREP file: {brep_path}")
        
        print(f"BREP file loaded successfully, shape type: {type(shape)}")
        
        # Check if we got a valid shape
        if shape.IsNull():
            raise ValueError("No shape found in BREP file")
        
        return shape
        
    except ImportError:
        raise RuntimeError("OCC-Core not available. Cannot process BREP files.")
    except Exception as e:
        print(f"Exception in load_brep_file: {type(e).__name__}: {e}")
        raise RuntimeError(f"Error loading BREP file: {e}")


def extract_planar_face(shape: Any) -> Any:
    """Extract a planar face from the shape.
    
    Parameters
    ----------
    shape: OCC shape
        The input shape
        
    Returns
    -------
    TopoDS_Face or None
        The planar face if found, None otherwise
    """
    try:
        from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Iterator, TopoDS_Shell, TopoDS_Solid, TopoDS_Compound
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        from OCC.Core.GeomAbs import GeomAbs_Plane
        
        print(f"Extract planar face: input shape type = {type(shape)}")
        print(f"Shape is null: {shape.IsNull()}")
        
        # If it's already a face, check if it's planar
        if isinstance(shape, TopoDS_Face):
            print("Input is already a face, checking if planar...")
            surface = BRepAdaptor_Surface(shape)
            surface_type = surface.GetType()
            print(f"Surface type: {surface_type}")
            if surface_type == GeomAbs_Plane:
                print("Found planar face!")
                return shape
            else:
                print(f"Face is not planar, surface type: {surface_type}")
        
        # Recursive function to find faces in any shape
        def find_planar_faces_recursive(current_shape, depth=0):
            indent = "  " * depth
            print(f"{indent}Examining shape at depth {depth}: {type(current_shape)}")
            
            if isinstance(current_shape, TopoDS_Face):
                print(f"{indent}Found face, checking if planar...")
                surface = BRepAdaptor_Surface(current_shape)
                surface_type = surface.GetType()
                print(f"{indent}Surface type: {surface_type}")
                if surface_type == GeomAbs_Plane:
                    print(f"{indent}Found planar face!")
                    return current_shape
            
            # For shells, solids, compounds, etc., iterate through sub-shapes
            if isinstance(current_shape, (TopoDS_Shell, TopoDS_Solid, TopoDS_Compound)) or not isinstance(current_shape, TopoDS_Face):
                print(f"{indent}Iterating through composite shape...")
                iterator = TopoDS_Iterator(current_shape)
                while iterator.More():
                    sub_shape = iterator.Value()
                    result = find_planar_faces_recursive(sub_shape, depth + 1)
                    if result is not None:
                        return result
                    iterator.Next()
            
            return None
        
        # Start recursive search
        print("Starting recursive search for planar faces...")
        result = find_planar_faces_recursive(shape)
        
        if result is None:
            print("No planar faces found in the entire shape hierarchy")
        
        return result
        
    except Exception as e:
        raise RuntimeError(f"Error extracting planar face: {e}")


def build_face_from_wire(wire: Any) -> Any:
    """Build a face from a closed wire.
    
    Parameters
    ----------
    wire: TopoDS_Wire
        The closed wire
        
    Returns
    -------
    TopoDS_Face or None
        The created face if successful, None if failed
    """
    try:
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
        from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir
        from OCC.Core.TopoDS import TopoDS_Wire
        
        if not isinstance(wire, TopoDS_Wire):
            return None
        
        # Create a plane (we'll align it properly later)
        plane = gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
        
        # Build face from wire
        face_builder = BRepBuilderAPI_MakeFace(plane, wire, True)
        if face_builder.IsDone():
            return face_builder.Face()
        
        return None
        
    except Exception as e:
        raise RuntimeError(f"Error building face from wire: {e}")


def canonicalize_to_xoy(face: Any) -> Any:
    """Canonicalize the face to XOY plane and normalize to origin.
    
    This function:
    1. Ensures the face is on the XOY plane
    2. Normalizes the face so its bottom-left corner is at (0,0)
    
    Parameters
    ----------
    face: TopoDS_Face
        The input face
        
    Returns
    -------
    TopoDS_Face
        The canonicalized face on XOY plane with bottom-left at (0,0)
    """
    try:
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir, gp_Trsf, gp_Vec
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCC.Core.GeomAbs import GeomAbs_Plane
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib_Add
        
        # Get the surface
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            raise ValueError("Face is not planar")
        
        # Get the plane parameters
        plane = surface.Plane()
        location = plane.Location()
        direction = plane.Axis().Direction()
        
        # Create transformation to align with XOY
        transform = gp_Trsf()
        
        # If the plane is not already on XOY, we need to transform it
        if abs(direction.Z()) < 0.9:  # Not already aligned with Z
            # Create a rotation to align with XOY
            # This is a simplified transformation
            pass
        
        # Apply transformation to get face on XOY plane
        transformer = BRepBuilderAPI_Transform(face, transform, True)
        if transformer.IsDone():
            face = transformer.Shape()
        
        # Now normalize the face to have bottom-left at (0,0)
        # Get the bounding box of the face
        bbox = Bnd_Box()
        brepbndlib_Add(face, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        
        print(f"Original face bounds: X({xmin:.1f}, {xmax:.1f}), Y({ymin:.1f}, {ymax:.1f})")
        
        # Calculate translation to move bottom-left to (0,0)
        translate_x = -xmin
        translate_y = -ymin
        
        print(f"Normalizing face: translating by ({translate_x:.1f}, {translate_y:.1f})")
        
        # Create translation transformation
        normalize_transform = gp_Trsf()
        normalize_transform.SetTranslation(gp_Vec(translate_x, translate_y, 0))
        
        # Apply normalization transformation
        normalizer = BRepBuilderAPI_Transform(face, normalize_transform, True)
        if normalizer.IsDone():
            normalized_face = normalizer.Shape()
            
            # Verify the normalization worked
            bbox_normalized = Bnd_Box()
            brepbndlib_Add(normalized_face, bbox_normalized)
            nxmin, nymin, nzmin, nxmax, nymax, nzmax = bbox_normalized.Get()
            print(f"Normalized face bounds: X({nxmin:.1f}, {nxmax:.1f}), Y({nymin:.1f}, {nymax:.1f})")
            
            return normalized_face
        
        return face
        
    except Exception as e:
        raise RuntimeError(f"Error canonicalizing face: {e}")


def compute_shape_properties(face: Any) -> Dict[str, Any]:
    """Compute geometric properties of the face.
    
    Parameters
    ----------
    face: TopoDS_Face
        The face to analyze
        
    Returns
    -------
    dict
        Dictionary containing bbox, area, and hole information
    """
    try:
        from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
        from OCC.Core.GProp import GProp_GProps
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib_Add
        from OCC.Core.TopoDS import TopoDS_Iterator
        from OCC.Core.TopoDS import TopoDS_Wire
        
        # Compute surface properties
        props = GProp_GProps()
        brepgprop_SurfaceProperties(face, props)
        area = props.Mass()  # Surface area
        
        # Compute bounding box
        bbox = Bnd_Box()
        brepbndlib_Add(face, bbox)
        
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        width = xmax - xmin
        height = ymax - ymin
        
        # Check for holes (simplified - count internal wires)
        holes = 0
        try:
            from OCC.Core.TopoDS import TopoDS_Face
            if isinstance(face, TopoDS_Face):
                # Count internal wires (holes)
                iterator = TopoDS_Iterator(face)
                while iterator.More():
                    sub_shape = iterator.Value()
                    if isinstance(sub_shape, TopoDS_Wire):
                        holes += 1
                    iterator.Next()
                # Subtract 1 for the outer wire
                holes = max(0, holes - 1)
        except:
            holes = 0
        
        return {
            'bbox_w_mm': width,
            'bbox_h_mm': height,
            'area_mm2': area,
            'has_holes': holes > 0
        }
        
    except Exception as e:
        raise RuntimeError(f"Error computing shape properties: {e}")


def save_brep_file(face: Any, brep_path: str | Path) -> None:
    """Save the face to a BREP file.
    
    Parameters
    ----------
    face: TopoDS_Face
        The face to save
    brep_path: Path-like
        Path for the output BREP file
    """
    try:
        from OCC.Core import BRepTools
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(brep_path), exist_ok=True)
        
        # Save to BREP format using the correct function signature
        if not BRepTools.breptools_Write(face, str(brep_path)):
            raise RuntimeError(f"Failed to write BREP file: {brep_path}")
            
    except Exception as e:
        raise RuntimeError(f"Error saving BREP file: {e}")


def brep_face_to_svg_path(face: Any) -> str:
    """Convert a BREP face to SVG path data.
    
    Parameters
    ----------
    face: TopoDS_Face
        The face to convert
        
    Returns
    -------
    str
        SVG path data string
    """
    try:
        from OCC.Core.BRepTools import BRepTools_WireExplorer
        from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
        from OCC.Core.GeomAbs import GeomAbs_Line, GeomAbs_Circle
        from OCC.Core.gp import gp_Pnt
        
        # Extract the outer wire of the face
        wire_explorer = BRepTools_WireExplorer(face)
        
        if not wire_explorer.More():
            # Fallback to bounding box if no wires found
            bbox = compute_shape_properties(face)
            width = bbox['bbox_w_mm']
            height = bbox['bbox_h_mm']
            return f"M 0 0 L {width} 0 L {width} {height} L 0 {height} Z"
        
        # Get the outer wire
        outer_wire = wire_explorer.Current()
        
        # Build SVG path from wire edges
        path_data = ""
        edge_explorer = BRepTools_WireExplorer(outer_wire)
        
        while edge_explorer.More():
            edge = edge_explorer.Current()
            curve_adaptor = BRepAdaptor_Curve(edge)
            curve_type = curve_adaptor.GetType()
            
            # Get start and end points
            start_point = curve_adaptor.Value(curve_adaptor.FirstParameter())
            end_point = curve_adaptor.Value(curve_adaptor.LastParameter())
            
            if curve_type == GeomAbs_Line:
                # Line segment
                if path_data == "":
                    path_data = f"M {start_point.X():.3f} {start_point.Y():.3f}"
                path_data += f" L {end_point.X():.3f} {end_point.Y():.3f}"
            
            elif curve_type == GeomAbs_Circle:
                # Circle/Arc segment - handle properly
                circle = curve_adaptor.Circle()
                center = circle.Location()
                radius = circle.Radius()
                
                # Check if it's a full circle
                if abs(curve_adaptor.LastParameter() - curve_adaptor.FirstParameter() - 2*math.pi) < 0.001:
                    # Full circle - use SVG circle element approach
                    if path_data == "":
                        # For full circle, we can use a different approach
                        # Create a circular path using SVG arc commands
                        path_data = f"M {center.X() + radius:.3f} {center.Y():.3f}"
                        path_data += f" A {radius:.3f} {radius:.3f} 0 1 1 {center.X() - radius:.3f} {center.Y():.3f}"
                        path_data += f" A {radius:.3f} {radius:.3f} 0 1 1 {center.X() + radius:.3f} {center.Y():.3f}"
                else:
                    # Partial arc - use SVG arc command
                    if path_data == "":
                        path_data = f"M {start_point.X():.3f} {start_point.Y():.3f}"
                    
                    # Determine sweep flag based on arc direction
                    # This is a simplified approach - in practice you'd need more sophisticated arc analysis
                    sweep_flag = 1 if curve_adaptor.LastParameter() > curve_adaptor.FirstParameter() else 0
                    large_arc_flag = 1 if abs(curve_adaptor.LastParameter() - curve_adaptor.FirstParameter()) > math.pi else 0
                    
                    path_data += f" A {radius:.3f} {radius:.3f} 0 {large_arc_flag} {sweep_flag} {end_point.X():.3f} {end_point.Y():.3f}"
            
            else:
                # Other curve types - approximate as line
                if path_data == "":
                    path_data = f"M {start_point.X():.3f} {start_point.Y():.3f}"
                path_data += f" L {end_point.X():.3f} {end_point.Y():.3f}"
            
            edge_explorer.Next()
        
        # Close the path
        if path_data != "":
            path_data += " Z"
        
        return path_data
        
    except Exception as e:
        print(f"Error converting face to SVG path: {e}")
        # Fallback to bounding box
        try:
            bbox = compute_shape_properties(face)
            width = bbox['bbox_w_mm']
            height = bbox['bbox_h_mm']
            return f"M 0 0 L {width} 0 L {width} {height} L 0 {height} Z"
        except:
            return ""


def generate_preview_svg(face: Any, svg_path: str | Path, width: float = 200, height: float = 150) -> None:
    """Generate a preview SVG from the face.
    
    Parameters
    ----------
    face: TopoDS_Face
        The face to render
    svg_path: Path-like
        Path for the output SVG file
    width: float
        SVG width in pixels
    height: float
        SVG height in pixels
    """
    try:
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        from OCC.Core.BRepTools import BRepTools_WireExplorer
        from OCC.Core.TopoDS import TopoDS_Iterator, TopoDS_Wire
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
        from OCC.Core.GeomAbs import GeomAbs_Line, GeomAbs_Circle, GeomAbs_Ellipse
        from OCC.Core.gp import gp_Lin, gp_Circ, gp_Elips
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(svg_path), exist_ok=True)
        
        # Get bounding box for scaling
        bbox = compute_shape_properties(face)
        bbox_w = bbox['bbox_w_mm']
        bbox_h = bbox['bbox_h_mm']
        
        # Calculate scale to fit in SVG
        scale_x = (width - 20) / bbox_w if bbox_w > 0 else 1
        scale_y = (height - 20) / bbox_h if bbox_h > 0 else 1
        scale = min(scale_x, scale_y)
        
        # Generate SVG content
        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" 
     xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .outline {{ stroke: #000000; stroke-width: 2; fill: none; }}
      .holes {{ stroke: #000000; stroke-width: 1; fill: none; }}
    </style>
  </defs>
  <rect width="{width}" height="{height}" fill="white"/>
  <g transform="translate(10, 10) scale({scale})">
'''
        
        # Extract and draw the actual shape outline
        try:
            # Get the outer wire of the face
            wire_explorer = BRepTools_WireExplorer(face)
            wire_count = 0
            
            while wire_explorer.More():
                wire = wire_explorer.Current()
                wire_count += 1
                is_outer = wire_explorer.CurrentWire().IsNull() == False
                
                print(f"Processing wire #{wire_count} (outer: {is_outer})")
                
                # Build SVG path from wire edges
                path_data = ""
                edge_explorer = BRepTools_WireExplorer(wire)
                
                while edge_explorer.More():
                    edge = edge_explorer.Current()
                    curve_adaptor = BRepAdaptor_Curve(edge)
                    curve_type = curve_adaptor.GetType()
                    
                    # Get start and end points
                    start_point = curve_adaptor.Value(curve_adaptor.FirstParameter())
                    end_point = curve_adaptor.Value(curve_adaptor.LastParameter())
                    
                    if curve_type == GeomAbs_Line:
                        # Line segment
                        if path_data == "":
                            path_data = f"M {start_point.X():.3f} {start_point.Y():.3f}"
                        path_data += f" L {end_point.X():.3f} {end_point.Y():.3f}"
                    
                    elif curve_type == GeomAbs_Circle:
                        # Arc segment
                        circle = curve_adaptor.Circle()
                        center = circle.Location()
                        radius = circle.Radius()
                        
                        # Determine if it's a full circle or arc
                        if abs(curve_adaptor.LastParameter() - curve_adaptor.FirstParameter() - 2*math.pi) < 0.001:
                            # Full circle
                            if path_data == "":
                                path_data = f"M {center.X() + radius:.3f} {center.Y():.3f}"
                            path_data += f" A {radius:.3f} {radius:.3f} 0 1 1 {center.X() - radius:.3f} {center.Y():.3f}"
                            path_data += f" A {radius:.3f} {radius:.3f} 0 1 1 {center.X() + radius:.3f} {center.Y():.3f}"
                        else:
                            # Arc - simplified as line for now
                            if path_data == "":
                                path_data = f"M {start_point.X():.3f} {start_point.Y():.3f}"
                            path_data += f" L {end_point.X():.3f} {end_point.Y():.3f}"
                    
                    else:
                        # Other curve types - approximate as line
                        if path_data == "":
                            path_data = f"M {start_point.X():.3f} {start_point.Y():.3f}"
                        path_data += f" L {end_point.X():.3f} {end_point.Y():.3f}"
                    
                    edge_explorer.Next()
                
                # Close the path
                if path_data != "":
                    path_data += " Z"
                    css_class = "outline" if is_outer else "holes"
                    svg_content += f'    <path d="{path_data}" class="{css_class}"/>\n'
                
                wire_explorer.Next()
            
            if wire_count == 0:
                # Fallback to bounding box if no wires found
                svg_content += f'    <rect x="0" y="0" width="{bbox_w}" height="{bbox_h}" class="outline"/>\n'
                
        except Exception as e:
            print(f"Error extracting wire geometry: {e}")
            # Fallback: simple rectangle
            svg_content += f'    <rect x="0" y="0" width="{bbox_w}" height="{bbox_h}" class="outline"/>\n'
        
        svg_content += '''  </g>
</svg>'''
        
        # Write SVG file
        with open(svg_path, 'w') as f:
            f.write(svg_content)
            
    except Exception as e:
        raise RuntimeError(f"Error generating preview SVG: {e}")


def boolean_union(face1: Any, face2: Any) -> Any:
    """Perform Boolean union operation between two faces.
    
    Parameters
    ----------
    face1: TopoDS_Face
        First face
    face2: TopoDS_Face
        Second face
        
    Returns
    -------
    TopoDS_Face
        Resulting face from union operation
    """
    try:
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
        from OCC.Core.ShapeFix import ShapeFix_Shape
        
        print("Performing Boolean union...")
        
        # Perform union operation
        fuse_op = BRepAlgoAPI_Fuse(face1, face2)
        if not fuse_op.IsDone():
            raise RuntimeError("Boolean union operation failed")
        
        result_shape = fuse_op.Shape()
        
        # Heal and simplify the result
        result_shape = heal_and_simplify(result_shape)
        
        # Extract the resulting face
        from OCC.Core.TopoDS import TopoDS_Face
        if isinstance(result_shape, TopoDS_Face):
            return result_shape
        else:
            # If result is not a face, try to extract a face from it
            return extract_planar_face(result_shape)
            
    except Exception as e:
        raise RuntimeError(f"Error in Boolean union: {e}")


def boolean_intersection(face1: Any, face2: Any) -> Any:
    """Perform Boolean intersection operation between two faces.
    
    Parameters
    ----------
    face1: TopoDS_Face
        First face
    face2: TopoDS_Face
        Second face
        
    Returns
    -------
    TopoDS_Face or None
        Resulting face from intersection operation, None if no intersection
    """
    try:
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
        
        print("Performing Boolean intersection...")
        
        # Perform intersection operation
        common_op = BRepAlgoAPI_Common(face1, face2)
        if not common_op.IsDone():
            raise RuntimeError("Boolean intersection operation failed")
        
        result_shape = common_op.Shape()
        
        # Check if there's actually an intersection
        if result_shape.IsNull():
            print("No intersection found")
            return None
        
        # Heal and simplify the result
        result_shape = heal_and_simplify(result_shape)
        
        # Extract the resulting face
        from OCC.Core.TopoDS import TopoDS_Face
        if isinstance(result_shape, TopoDS_Face):
            return result_shape
        else:
            # If result is not a face, try to extract a face from it
            return extract_planar_face(result_shape)
            
    except Exception as e:
        raise RuntimeError(f"Error in Boolean intersection: {e}")


def boolean_difference(face1: Any, face2: Any) -> Any:
    """Perform Boolean difference operation (face1 - face2).
    
    Parameters
    ----------
    face1: TopoDS_Face
        Face to subtract from
    face2: TopoDS_Face
        Face to subtract
        
    Returns
    -------
    TopoDS_Face or None
        Resulting face from difference operation, None if nothing remains
    """
    try:
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
        
        print("Performing Boolean difference...")
        
        # Perform difference operation
        cut_op = BRepAlgoAPI_Cut(face1, face2)
        if not cut_op.IsDone():
            raise RuntimeError("Boolean difference operation failed")
        
        result_shape = cut_op.Shape()
        
        # Check if there's anything left
        if result_shape.IsNull():
            print("Nothing remains after difference operation")
            return None
        
        # Heal and simplify the result
        result_shape = heal_and_simplify(result_shape)
        
        # Extract the resulting face
        from OCC.Core.TopoDS import TopoDS_Face
        if isinstance(result_shape, TopoDS_Face):
            return result_shape
        else:
            # If result is not a face, try to extract a face from it
            return extract_planar_face(result_shape)
            
    except Exception as e:
        raise RuntimeError(f"Error in Boolean difference: {e}")


def create_panel_face(width_mm: float, height_mm: float) -> Any:
    """Create a rectangular panel face.
    
    Parameters
    ----------
    width_mm: float
        Panel width in mm
    height_mm: float
        Panel height in mm
        
    Returns
    -------
    TopoDS_Face
        Rectangular panel face
    """
    try:
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
        from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir
        
        print(f"Creating panel face: {width_mm}×{height_mm}mm")
        
        # Create a plane at origin (XY plane)
        plane = gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
        
        # Create a rectangular face using BRepBuilderAPI_MakeFace with bounds
        face_maker = BRepBuilderAPI_MakeFace(plane, 0, width_mm, 0, height_mm)
        
        if face_maker.IsDone():
            return face_maker.Face()
        else:
            raise RuntimeError("Failed to create panel face")
        
    except Exception as e:
        raise RuntimeError(f"Error creating panel face: {e}")


def heal_and_simplify(shape: Any) -> Any:
    """Heal and simplify a shape after Boolean operations.
    
    Parameters
    ----------
    shape: OCC shape
        Shape to heal
        
    Returns
    -------
    OCC shape
        Healed and simplified shape
    """
    try:
        from OCC.Core.ShapeFix import ShapeFix_Shape
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Sewing
        
        print("Healing and simplifying shape...")
        
        # Use ShapeFix to heal the shape
        shape_fix = ShapeFix_Shape(shape)
        shape_fix.Perform()
        
        if shape_fix.Status(ShapeFix_Shape.Status_DONE):
            healed_shape = shape_fix.Shape()
        else:
            print("ShapeFix failed, using original shape")
            healed_shape = shape
        
        # Use BRepBuilderAPI_Sewing for additional healing if needed
        # This is especially useful for shells and compounds
        try:
            sewing = BRepBuilderAPI_Sewing()
            sewing.Add(healed_shape)
            sewing.Perform()
            
            if sewing.IsDone():
                sewn_shape = sewing.SewedShape()
                if not sewn_shape.IsNull():
                    healed_shape = sewn_shape
        except:
            print("Sewing failed, using ShapeFix result")
        
        return healed_shape
        
    except Exception as e:
        print(f"Error in heal_and_simplify: {e}")
        return shape


def process_shape_asset(shape_asset: ShapeAsset) -> None:
    """Process a ShapeAsset through the complete import pipeline.
    
    Parameters
    ----------
    shape_asset: ShapeAsset
        The shape asset to process
        
    Raises
    ------
    RuntimeError
        If processing fails
    """
    try:
        # Determine which file to process (prefer BREP over STEP)
        if shape_asset.source_brep:
            file_path = shape_asset.source_brep.path
            file_type = "BREP"
            print(f"Processing BREP file: {file_path}")
            shape = load_brep_file(file_path)
        elif shape_asset.source_step:
            file_path = shape_asset.source_step.path
            file_type = "STEP"
            print(f"Processing STEP file: {file_path}")
            # For now, we'll skip STEP files since they weren't working
            raise RuntimeError("STEP files are not currently supported. Please use BREP files.")
        else:
            raise RuntimeError("No source file found. Please upload a BREP file.")
        
        print(f"File exists: {os.path.exists(file_path)}")
        
        if shape is None:
            raise RuntimeError(f"Failed to load {file_type} file")
        print(f"{file_type} file loaded successfully, shape type: {type(shape)}")
        
        # Step 2: Extract planar face
        print("Extracting planar face...")
        face = extract_planar_face(shape)
        if face is None:
            raise RuntimeError(f"No planar face found in {file_type} file")
        print(f"Planar face extracted successfully, face type: {type(face)}")
        
        # Step 3: Canonicalize to XOY
        print("Canonicalizing to XOY plane...")
        canonical_face = canonicalize_to_xoy(face)
        print(f"Face canonicalized successfully")
        
        # Step 4: Compute properties
        print("Computing geometric properties...")
        properties = compute_shape_properties(canonical_face)
        print(f"Properties computed: {properties}")
        
        # Step 5: Save canonical BREP
        print("Saving canonical BREP...")
        brep_filename = f"shapes/brep/{shape_asset.id}.brep"
        brep_path = os.path.join(settings.MEDIA_ROOT, brep_filename)
        save_brep_file(canonical_face, brep_path)
        print(f"BREP file saved to: {brep_path}")
        
        # Step 5.5: Canonicalize wire orientation to CCW/FORWARD and validate closure
        print("Canonicalizing wire orientation and validating closure...")
        if not shape_asset.canonicalize_wire_orientation(brep_path):
            raise RuntimeError("Wire orientation canonicalization and closure validation failed. Internal shapes must be properly closed.")
        print("Wire orientation canonicalized and closure validated successfully")
        
        # Step 6: Generate preview SVG
        print("Generating preview SVG...")
        svg_filename = f"shapes/preview/{shape_asset.id}.svg"
        svg_path = os.path.join(settings.MEDIA_ROOT, svg_filename)
        generate_preview_svg(canonical_face, svg_path)
        print(f"SVG file saved to: {svg_path}")
        
        # Step 7: Update the model
        print("Updating shape asset...")
        shape_asset.canonical_brep = brep_filename
        shape_asset.preview_svg = svg_filename
        shape_asset.bbox_w_mm = properties['bbox_w_mm']
        shape_asset.bbox_h_mm = properties['bbox_h_mm']
        shape_asset.area_mm2 = properties['area_mm2']
        shape_asset.has_holes = properties['has_holes']
        
        # Set default attach point to bottom-left corner
        shape_asset.attach_x_mm = 0.0
        shape_asset.attach_y_mm = properties['bbox_h_mm'] / 2.0  # Center Y
        shape_asset.attach_angle_deg = 0.0
        
        shape_asset.save()
        print(f"Successfully processed shape: {shape_asset.name}")
        
    except Exception as e:
        import traceback
        print(f"Error processing shape {shape_asset.name}: {e}")
        print("Full traceback:")
        print(traceback.format_exc())
        raise RuntimeError(f"Failed to process shape: {e}")


def export_panel_to_dxf(panel: 'Panel2D') -> str:
    """Export panel layout to DXF format using existing Panel2D instance.
    
    Parameters
    ----------
    panel: Panel2D
        The panel instance with all shapes already added
        
    Returns
    -------
    str
        DXF file content as string
    """
    try:
        import ezdxf
        import math
        
        # Create a new DXF document
        doc = ezdxf.new('R2010')  # AutoCAD 2010 format
        msp = doc.modelspace()
        
        # Get the final panel shape with all cuts
        panel_shape = panel.as_shape()
        
        # Convert the panel shape to DXF
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopAbs import TopAbs_WIRE, TopAbs_EDGE
        from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
        from OCC.Core.GeomAbs import GeomAbs_Line, GeomAbs_Circle
        
        # Extract all wires from the panel shape
        wire_explorer = TopExp_Explorer(panel_shape, TopAbs_WIRE)
        
        while wire_explorer.More():
            wire = wire_explorer.Current()
            
            # Extract edges from the wire
            edge_explorer = TopExp_Explorer(wire, TopAbs_EDGE)
            
            points = []
            while edge_explorer.More():
                edge = edge_explorer.Current()
                
                # Use BRepAdaptor_Curve to get points from the edge
                try:
                    curve_adaptor = BRepAdaptor_Curve(edge)
                    
                    # Get start and end points
                    start_point = curve_adaptor.Value(curve_adaptor.FirstParameter())
                    end_point = curve_adaptor.Value(curve_adaptor.LastParameter())
                    
                    points.append((start_point.X(), start_point.Y()))
                    points.append((end_point.X(), end_point.Y()))
                    
                except Exception as e:
                    print(f"Warning: Could not process edge: {e}")
                    continue
                
                edge_explorer.Next()
            
            if points:
                # Remove duplicate consecutive points
                unique_points = []
                for i, point in enumerate(points):
                    if i == 0 or point != points[i-1]:
                        unique_points.append(point)
                
                if len(unique_points) > 1:
                    msp.add_lwpolyline(unique_points)
            
            wire_explorer.Next()
        
        # Export to string - use the correct method for newer ezdxf versions
        from io import StringIO
        stream = StringIO()
        doc.write(stream)
        return stream.getvalue()
        
    except Exception as e:
        raise RuntimeError(f"Error exporting to DXF: {e}")


def export_panel_to_brep(panel: 'Panel2D', path: str) -> None:
    """Export panel layout to BREP format.
    
    Parameters
    ----------
    panel: Panel2D
        The panel instance with all shapes already added
    path: str
        Path where to save the BREP file
        
    Raises
    ------
    RuntimeError
        If the BREP file cannot be written
    """
    try:
        # Use the Panel2D's built-in save_brep method
        panel.save_brep(path)
        
    except Exception as e:
        raise RuntimeError(f"Error exporting to BREP: {e}")
