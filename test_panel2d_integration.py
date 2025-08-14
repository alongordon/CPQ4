#!/usr/bin/env python3
"""
Test script for Panel2D integration with ShapeAsset model.
Demonstrates how to use the new shape_type field with Panel2D.
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cpq4.settings')
django.setup()

from shapes.models import ShapeAsset
from panel2d import Panel2D

def test_panel2d_integration():
    """Test the integration between ShapeAsset and Panel2D."""
    
    print("=== Panel2D Integration Test ===\n")
    
    # 1. Create a panel
    panel = Panel2D(width=800.0, height=1900.0)
    print(f"Created panel: {panel}")
    
    # 2. Get all processed shapes from the database
    shapes = ShapeAsset.objects.filter(canonical_brep__isnull=False)
    print(f"\nFound {shapes.count()} processed shapes in database:")
    
    for shape in shapes:
        print(f"  - {shape.name} ({shape.shape_type}) - {shape.get_bbox_display()}")
    
    # 3. Add shapes to the panel based on their type
    edge_shapes = shapes.filter(shape_type='edge_affecting')
    internal_shapes = shapes.filter(shape_type='internal_cutout')
    
    print(f"\nEdge-affecting shapes: {edge_shapes.count()}")
    print(f"Internal cutout shapes: {internal_shapes.count()}")
    
    # 4. Add edge-affecting shapes first (they modify the boundary)
    for shape in edge_shapes:
        try:
            # Use the helper method
            shape.add_to_panel2d(panel, tx=0, ty=100, angle_deg=0, scale=1.0)
            print(f"  ✓ Added {shape.name} as edge-affecting shape")
        except Exception as e:
            print(f"  ✗ Failed to add {shape.name}: {e}")
    
    # 5. Add internal cutout shapes
    for shape in internal_shapes:
        try:
            # Use the helper method
            shape.add_to_panel2d(panel, tx=400, ty=950, angle_deg=0, scale=1.0)
            print(f"  ✓ Added {shape.name} as internal cutout")
        except Exception as e:
            print(f"  ✗ Failed to add {shape.name}: {e}")
    
    # 6. Get final panel info
    edge_count, inner_count = panel.get_library_shapes_count()
    print(f"\nFinal panel: {edge_count} edge cuts, {inner_count} internal cuts")
    
    # 7. Build the final shape
    try:
        final_shape = panel.as_shape()
        print("✓ Successfully built final panel shape")
        
        # You could save this to a file or display it
        # from OCC.Core.BRepTools import breptools_Write
        # breptools_Write(final_shape, "final_panel.brep")
        
    except Exception as e:
        print(f"✗ Failed to build final shape: {e}")
    
    return panel

def update_existing_shapes():
    """Update existing shapes to have appropriate shape_type values."""
    print("\n=== Updating Existing Shapes ===\n")
    
    # Get all shapes without a shape_type (they'll have the default 'internal_cutout')
    shapes = ShapeAsset.objects.all()
    
    for shape in shapes:
        # You can set logic here to determine the appropriate type
        # For now, let's set them all as internal cutouts
        if shape.shape_type == 'internal_cutout':  # default value
            # You could add logic here to determine if it should be edge_affecting
            # For example, based on the shape name or properties
            if 'notch' in shape.name.lower() or 'slot' in shape.name.lower():
                shape.shape_type = 'edge_affecting'
                shape.save()
                print(f"  Set {shape.name} as edge_affecting")
            else:
                print(f"  {shape.name} remains as internal_cutout")

if __name__ == "__main__":
    # First, update existing shapes if needed
    update_existing_shapes()
    
    # Then test the integration
    panel = test_panel2d_integration()
    
    print("\n=== Test Complete ===")
    print("You can now:")
    print("1. Go to Django admin to set shape_type for your shapes")
    print("2. Use the panel.as_shape() method to get the final geometry")
    print("3. Use panel.view() to see the result in OCC viewer")
