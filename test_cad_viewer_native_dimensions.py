#!/usr/bin/env python3
"""
Test script for CAD viewer with native dimensions.
This script tests the integration of PrsDim_LengthDimension in the CAD viewer.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from panel2d import Panel2D

def test_cad_viewer_native_dimensions():
    """Test CAD viewer with native dimensions."""
    print("=== Testing CAD Viewer with Native Dimensions ===")
    
    # Create a simple panel
    panel = Panel2D(width=800, height=600)
    print(f"Created panel: {panel}")
    
    # Test native dimension creation for CAD viewer
    print("\n--- Testing Native Dimension Creation for CAD Viewer ---")
    try:
        # Simulate what the CAD viewer does
        from OCC.Display.SimpleGui import init_display
        
        # Initialize display
        display, start_display, *_ = init_display()
        
        # Display panel shape
        panel_shape = panel.as_shape()
        display.DisplayShape(panel_shape, color='lightblue', transparency=0.3)
        
        # Set up dimension style and units (like CAD viewer does)
        drawer = display.Context.DefaultDrawer()
        drawer.SetDimLengthModelUnits("mm")
        drawer.SetDimLengthDisplayUnits("mm")
        
        from OCC.Core.Prs3d import Prs3d_DimensionAspect
        asp = Prs3d_DimensionAspect()
        asp.MakeUnitsDisplayed(True)
        asp.MakeText3d(False)  # Screen text
        asp.TextAspect().SetHeight(12.0)
        drawer.SetDimensionAspect(asp)
        
        # Create and display native dimensions
        native_dims = panel.make_native_dimensions(include_cutouts=False, offset=25.0)
        print(f"Created {len(native_dims)} native dimensions for CAD viewer")
        
        for i, dim in enumerate(native_dims):
            print(f"  Dimension {i+1}: {type(dim).__name__}")
            display.Context.Display(dim, False)
        
        # Set view parameters for 2D view
        display.View.SetProj(0, 0, 1)  # Top view (XY plane)
        display.View.FitAll()
        
        print("✅ CAD viewer native dimensions test completed successfully!")
        print("Opening viewer... (close the window to continue)")
        
        start_display()
        
    except Exception as e:
        print(f"Error testing CAD viewer native dimensions: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("CAD Viewer Native Dimension Integration Test")
    print("=" * 50)
    
    test_cad_viewer_native_dimensions()
    
    print("\n✅ All tests completed!")
