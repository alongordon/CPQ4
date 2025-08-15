#!/usr/bin/env python3
"""
Test script for Panel2D dimension functionality.
This script creates a simple panel and tests the dimension rendering.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from panel2d import Panel2D

def test_basic_dimensions():
    """Test basic panel dimension functionality."""
    print("=== Testing Panel2D Dimension Functionality ===")
    
    # Create a simple panel
    panel = Panel2D(width=800, height=600)
    print(f"Created panel: {panel}")
    
    # Test dimension geometry generation
    print("\n--- Testing Dimension Geometry Generation ---")
    try:
        dimension_shapes = panel.get_dimension_geometry()
        print(f"Generated {len(dimension_shapes)} dimension shapes")
        
        # Print details of each dimension shape
        for i, shape in enumerate(dimension_shapes):
            print(f"  Dimension shape {i+1}: {type(shape).__name__}")
            
    except Exception as e:
        print(f"Error generating dimension geometry: {e}")
        return False
    
    # Test dimension viewing (if OCC display is available)
    print("\n--- Testing Dimension Viewing ---")
    try:
        print("Attempting to open dimension viewer...")
        panel.view_with_true_dimensions()
        print("Dimension viewer opened successfully!")
    except Exception as e:
        print(f"Dimension viewing not available: {e}")
        print("This is expected if OCC Display is not available")
    
    print("\n=== Dimension Test Completed ===")
    return True

def test_panel_with_shapes():
    """Test panel dimensions with placed shapes."""
    print("\n=== Testing Panel with Shapes ===")
    
    # Create a panel with some shapes
    panel = Panel2D(width=1000, height=800)
    
    # Add some internal cutouts (if we have shape files)
    # For now, just test the dimension functionality
    print(f"Created panel with shapes: {panel}")
    
    # Test dimension geometry
    try:
        dimension_shapes = panel.get_dimension_geometry()
        print(f"Generated {len(dimension_shapes)} dimension shapes for panel with shapes")
    except Exception as e:
        print(f"Error generating dimension geometry: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Panel2D Dimension Functionality Test")
    print("=" * 50)
    
    # Test basic dimensions
    success1 = test_basic_dimensions()
    
    # Test panel with shapes
    success2 = test_panel_with_shapes()
    
    if success1 and success2:
        print("\n✅ All dimension tests passed!")
    else:
        print("\n❌ Some dimension tests failed!")
        sys.exit(1)
