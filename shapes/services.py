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
        success = BRepTools.breptools_Read(shape, str(brep_path), builder)
        print(f"BRepTools.breptools_Read result: {success}")
        
        if not success:
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
    """Canonicalize the face to XOY plane.
    
    Parameters
    ----------
    face: TopoDS_Face
        The input face
        
    Returns
    -------
    TopoDS_Face
        The canonicalized face on XOY plane
    """
    try:
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir, gp_Trsf, gp_Ax3
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCC.Core.GeomAbs import GeomAbs_Plane
        
        # Get the surface
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            raise ValueError("Face is not planar")
        
        # Get the plane parameters
        plane = surface.Plane()
        location = plane.Location()
        direction = plane.Axis().Direction()
        
        # Create transformation to align with XOY
        # This is a simplified approach - in practice you'd want more robust alignment
        transform = gp_Trsf()
        
        # If the plane is not already on XOY, we need to transform it
        if abs(direction.Z()) < 0.9:  # Not already aligned with Z
            # Create a rotation to align with XOY
            # This is a simplified transformation
            pass
        
        # Apply transformation
        transformer = BRepBuilderAPI_Transform(face, transform, True)
        if transformer.IsDone():
            return transformer.Shape()
        
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
