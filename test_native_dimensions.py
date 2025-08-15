#!/usr/bin/env python3
"""
Test script for Panel2D native dimension functionality.
This script tests the new PrsDim_LengthDimension approach.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from panel2d import Panel2D

def test_native_dimensions():
    """Test native dimension functionality."""
    print("=== Testing Panel2D Native Dimension Functionality ===")
    
    # Create a simple panel
    panel = Panel2D(width=800, height=600)
    print(f"Created panel: {panel}")
    
    # Test native dimension creation
    print("\n--- Testing Native Dimension Creation ---")
    try:
        dims = panel.make_native_dimensions(include_cutouts=False, offset=25.0)
        print(f"Created {len(dims)} native dimensions")
        for i, dim in enumerate(dims):
            print(f"  Dimension {i+1}: {type(dim).__name__}")
        
        # Test native dimension viewing
        print("\n--- Testing Native Dimension Viewing ---")
        print("Attempting to open native dimension viewer...")
        panel.view_with_native_dimensions(include_cutouts=False, offset=25.0, units="mm", show_units=True)
        print("Native dimension viewer opened successfully!")
        
    except Exception as e:
        print(f"Error testing native dimensions: {e}")
        import traceback
        traceback.print_exc()

def test_panel_with_cutouts():
    """Test native dimensions with cutouts."""
    print("\n=== Testing Panel with Cutouts ===")
    
    # Create a panel with some internal cutouts
    panel = Panel2D(width=1000, height=800)
    
    # Add a simple rectangular cutout
    panel.add_library_shape(
        path="shapes/rectangle_100x50.brep",  # This would need to exist
        kind="internal_cutout",
        tx=200,  # 200mm from left edge
        ty=100   # 100mm from top edge
    )
    
    print(f"Created panel with cutouts: {panel}")
    
    try:
        dims = panel.make_native_dimensions(include_cutouts=True, offset=30.0)
        print(f"Created {len(dims)} native dimensions (including cutouts)")
        
        # Test viewing with cutouts
        print("Attempting to open native dimension viewer with cutouts...")
        panel.view_with_native_dimensions(include_cutouts=True, offset=30.0, units="mm", show_units=True)
        print("Native dimension viewer with cutouts opened successfully!")
        
    except Exception as e:
        print(f"Error testing native dimensions with cutouts: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Panel2D Native Dimension Functionality Test")
    print("=" * 50)
    
    test_native_dimensions()
    test_panel_with_cutouts()
    
    print("\n✅ Native dimension tests completed!")
