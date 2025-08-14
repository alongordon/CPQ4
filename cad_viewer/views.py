from django.shortcuts import render
from django.http import JsonResponse
from shapes.models import ShapeAsset
import json
from shapes.services import (
    export_panel_to_dxf
)
from panel2d import Panel2D
from django.views.decorators.csrf import csrf_exempt
import base64
import io

def cad_viewer(request):
    """Main CAD viewer interface."""
    shapes = ShapeAsset.objects.filter(canonical_brep__isnull=False).order_by('name')
    context = {
        'shapes': shapes,
        'panel_width': 800,
        'panel_height': 1900,
        'panel_area': 800 * 1900,
    }
    return render(request, 'cad_viewer/cad_viewer.html', context)

def get_shapes_library(request):
    """API endpoint to get available shapes for the library."""
    try:
        shape_type = request.GET.get('shape_type', '')  # Optional filter
        
        # Get processed shapes
        shapes = ShapeAsset.objects.filter(canonical_brep__isnull=False)
        
        # Filter by shape type if specified
        if shape_type:
            shapes = shapes.filter(shape_type=shape_type)
        
        shapes_data = []
        for shape in shapes:
            shapes_data.append({
                'id': str(shape.id),
                'name': shape.name,
                'shape_type': shape.shape_type,
                'bbox_w_mm': shape.bbox_w_mm,
                'bbox_h_mm': shape.bbox_h_mm,
                'area_mm2': shape.area_mm2,
                'default_edge': shape.default_edge,
                'default_offset_mm': shape.default_offset_mm,
            })
        
        return JsonResponse({
            'shapes': shapes_data,
            'success': True
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



def render_brep_view(request):
    """Render BREP geometry using OCC-Core visualization."""
    try:
        # Get parameters from request
        panel_width = float(request.GET.get('panel_width', 800))
        panel_height = float(request.GET.get('panel_height', 1900))
        zoom_level = float(request.GET.get('zoom', 0.8))
        
        # Get placed shapes data
        placed_shapes = request.GET.get('placed_shapes', '[]')
        import json
        try:
            placed_shapes = json.loads(placed_shapes)
        except:
            placed_shapes = []
        
        # Create panel using Panel2D class
        panel = Panel2D(width=panel_width, height=panel_height)
        
        # Debug logging
        print(f"=== BACKEND RENDER DEBUG ===")
        print(f"Panel dimensions: {panel_width} x {panel_height}")
        print(f"Placed shapes count: {len(placed_shapes)}")
        print(f"Placed shapes data: {placed_shapes}")
        
        # Add placed shapes to the panel
        for i, shape_data in enumerate(placed_shapes):
            try:
                shape_id = shape_data.get('shape_id')
                shape_type = shape_data.get('shape_type')
                x = float(shape_data.get('x', 0))
                y = float(shape_data.get('y', 0))
                angle_deg = float(shape_data.get('angle_deg', 0))
                
                print(f"--- Processing shape {i+1} ---")
                print(f"Shape ID: {shape_id}")
                print(f"Shape type: {shape_type}")
                print(f"Coordinates: x={x}, y={y}")
                print(f"Angle: {angle_deg} degrees")
                
                # Get the shape from database
                shape_asset = ShapeAsset.objects.get(id=shape_id)
                print(f"Shape asset: {shape_asset.name}")
                print(f"Shape asset type: {shape_asset.shape_type}")
                
                # Add shape to panel using the helper method
                if shape_type == 'edge_affecting':
                    # For edge-affecting shapes, pass edge and position instead of tx/ty
                    edge = shape_data.get('edge')
                    position = float(shape_data.get('position', 0))
                    shape_asset.add_to_panel2d(panel, angle_deg=angle_deg, scale=1.0, edge=edge, position=position)
                else:
                    # For internal cutouts, use the original tx/ty approach
                    shape_asset.add_to_panel2d(panel, tx=x, ty=y, angle_deg=angle_deg, scale=1.0)
                print(f"Shape {i+1} added successfully")
                
            except Exception as e:
                print(f"Error adding shape {shape_id}: {e}")
                continue
        
        # Get the final panel shape with all cuts
        try:
            panel_shape = panel.as_shape()
        except Exception as e:
            return JsonResponse({'error': f'Failed to create panel shape: {e}'}, status=500)
        
        # Try OCC display first, fallback to SVG if it fails
        try:
            # Set matplotlib backend before importing OCC
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            
            # Import OCC display with error handling
            try:
                from OCC.Display.SimpleGui import init_display
            except ImportError as e:
                raise Exception(f'OCC Display not available: {e}')
            
            # Initialize OCC display with error handling
            try:
                # Try different display backends
                display = None
                for backend in ['qt-pyqt5', 'qt-pyside2', 'qt-pyqt4', 'wx']:
                    try:
                        display, start_display, add_menu, add_function_to_menu = init_display(size=(1200, 800), backend=backend)
                        break
                    except:
                        continue
                
                if display is None:
                    # Fallback to default backend
                    display, start_display, add_menu, add_function_to_menu = init_display(size=(1200, 800))
                    
            except Exception as e:
                raise Exception(f'Failed to initialize OCC display: {e}')
            
            # Display the shape
            display.DisplayShape(panel_shape, color='lightblue', transparency=0.3)
            
            # Set view parameters for 2D view
            display.View.SetProj(0, 0, 1)  # Top view (XY plane)
            display.View.FitAll()
            display.View.SetZoom(zoom_level)  # Use the requested zoom level
            
            # Capture the view as image
            import os
            import tempfile
            
            # Create a temporary file with absolute path
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f'temp_view_{os.getpid()}.png')
            
            try:
                # Dump the view to the temporary file
                display.View.Dump(temp_file)
                
                # Check if file was created and has content
                if not os.path.exists(temp_file):
                    raise RuntimeError("Failed to create image file")
                
                # Check file size
                file_size = os.path.getsize(temp_file)
                if file_size == 0:
                    raise RuntimeError("Image file is empty")
                
                # Read the image and convert to base64
                with open(temp_file, 'rb') as f:
                    image_data = f.read()
                    
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass  # Ignore cleanup errors
            
            # Return image as base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            return JsonResponse({
                'image': f'data:image/png;base64,{image_b64}',
                'success': True
            })
            
        except Exception as e:
            # Fallback to SVG generation
            print(f"OCC display failed, using SVG fallback: {e}")
            
            # Generate simple SVG representation
            svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{panel_width}" height="{panel_height}" xmlns="http://www.w3.org/2000/svg">
    <rect width="{panel_width}" height="{panel_height}" fill="lightblue" stroke="black" stroke-width="2"/>
    <text x="10" y="30" font-family="Arial" font-size="16" fill="black">Panel: {panel_width}mm × {panel_height}mm</text>
    <text x="10" y="50" font-family="Arial" font-size="12" fill="black">Shapes: {len(placed_shapes)}</text>
</svg>'''
            
            # Convert SVG to base64
            svg_b64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
            return JsonResponse({
                'image': f'data:image/svg+xml;base64,{svg_b64}',
                'success': True
            })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



@csrf_exempt
def export_to_dxf(request):
    """Export panel layout to DXF format."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

    try:
        data = json.loads(request.body)
        shapes_data = data.get('shapes', [])
        panel_width = data.get('panel_width', 800)
        panel_height = data.get('panel_height', 1900)

        # Create panel using Panel2D class (same as in render_brep_view)
        panel = Panel2D(width=panel_width, height=panel_height)
        
        # Add placed shapes to the panel
        for shape_data in shapes_data:
            try:
                shape_id = shape_data.get('id')
                shape_type = shape_data.get('shape_type')
                x = float(shape_data.get('x', 0))
                y = float(shape_data.get('y', 0))
                angle_deg = float(shape_data.get('angle_deg', 0))
                
                # Get the shape from database
                shape_asset = ShapeAsset.objects.get(id=shape_id)
                
                # Add shape to panel using the helper method
                if shape_type == 'edge_affecting':
                    # For edge-affecting shapes, pass edge and position instead of tx/ty
                    edge = shape_data.get('edge')
                    position = float(shape_data.get('position', 0))
                    shape_asset.add_to_panel2d(panel, angle_deg=angle_deg, scale=1.0, edge=edge, position=position)
                else:
                    # For internal cutouts, use the original tx/ty approach
                    shape_asset.add_to_panel2d(panel, tx=x, ty=y, angle_deg=angle_deg, scale=1.0)
                
            except Exception as e:
                print(f"Error adding shape {shape_id}: {e}")
                continue

        # Generate DXF content using the same panel instance
        dxf_content = export_panel_to_dxf(panel)

        # Return as downloadable file
        from django.http import HttpResponse
        response = HttpResponse(dxf_content, content_type='application/dxf')
        response['Content-Disposition'] = 'attachment; filename="panel_layout.dxf"'
        return response

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500) 

@csrf_exempt
def export_to_brep(request):
    """Export panel layout to BREP format."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

    try:
        data = json.loads(request.body)
        shapes_data = data.get('shapes', [])
        panel_width = data.get('panel_width', 800)
        panel_height = data.get('panel_height', 1900)

        # Create panel using Panel2D class (same as in render_brep_view)
        panel = Panel2D(width=panel_width, height=panel_height)
        
        # Add placed shapes to the panel
        for shape_data in shapes_data:
            try:
                shape_id = shape_data.get('id')
                shape_type = shape_data.get('shape_type')
                x = float(shape_data.get('x', 0))
                y = float(shape_data.get('y', 0))
                angle_deg = float(shape_data.get('angle_deg', 0))
                
                # Get the shape from database
                shape_asset = ShapeAsset.objects.get(id=shape_id)
                
                # Add shape to panel using the helper method
                if shape_type == 'edge_affecting':
                    # For edge-affecting shapes, pass edge and position instead of tx/ty
                    edge = shape_data.get('edge')
                    position = float(shape_data.get('position', 0))
                    shape_asset.add_to_panel2d(panel, angle_deg=angle_deg, scale=1.0, edge=edge, position=position)
                else:
                    # For internal cutouts, use the original tx/ty approach
                    shape_asset.add_to_panel2d(panel, tx=x, ty=y, angle_deg=angle_deg, scale=1.0)
                
            except Exception as e:
                print(f"Error adding shape {shape_id}: {e}")
                continue

        # Generate unique filename
        import uuid
        import os
        from django.conf import settings
        
        filename = f"panel_layout_{uuid.uuid4().hex[:8]}.brep"
        file_path = os.path.join(settings.MEDIA_ROOT, "exports", filename)
        
        # Ensure exports directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save BREP file using Panel2D's save_brep method
        panel.save_brep(file_path)

        # Return success response with file info
        return JsonResponse({
            'success': True,
            'filename': filename,
            'message': f'Panel exported to BREP file: {filename}'
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500) 
