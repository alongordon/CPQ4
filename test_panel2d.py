#!/usr/bin/env python3
"""
Test script for the evolved Panel2D class.
Demonstrates how to create a panel with library shapes and view it in OCC.
"""

from OCC.Display.SimpleGui import init_display
from panel2d import Panel2D
import os

def create_sample_brep_files():
    """Create sample BREP files for testing if they don't exist."""
    # This would normally come from your shape library
    # For now, we'll create simple test files
    pass

def main():
    # 1. Create the panel
    print("Creating panel...")
    panel = Panel2D(width=800.0, height=1900.0)
    
    # 2. Add library shapes (if BREP files exist)
    print("Adding library shapes...")
    
    # Example: Add a hinge notch that bites into the outer edge
    # panel.add_library_shape(
    #     path="hinge_notch.brep",
    #     kind="edge_affecting",
    #     tx=0, ty=1000, angle_deg=0, scale=1.0
    # )
    
    # Example: Add a handle hole fully inside the panel
    # panel.add_library_shape(
    #     path="handle_hole_profile.brep",
    #     kind="internal_cutout",
    #     tx=400, ty=1000, angle_deg=0, scale=1.0
    # )
    
    # For now, just show the base panel
    print("No BREP files found - showing base panel only")
    
    # 3. Get the final shape
    print("Building shape...")
    shape = panel.as_shape()
    
    print(f"Panel: {panel}")
    print(f"Dimensions: {panel.get_dimensions()}")
    edge_count, inner_count = panel.get_library_shapes_count()
    print(f"Library shapes: {edge_count} edge cuts, {inner_count} internal cuts")
    
    # 4. Start the OCC viewer
    print("Starting OCC viewer...")
    display, start_display, add_menu, add_function_to_menu = init_display()
    
    # 5. Display the shape
    print("Displaying shape...")
    display.DisplayShape(shape, color='lightblue', transparency=0.3, update=True)
    
    # 6. Set 2D view (top view - XY plane)
    print("Setting 2D view...")
    display.View.SetProj(0, 0, 1)  # Top view (XY plane)
    display.FitAll()
    
    # 7. Launch the interactive viewer loop
    print("Launching viewer... (close window to exit)")
    start_display()

def test_with_sample_shapes():
    """Test with some sample shapes if available."""
    panel = Panel2D(width=800.0, height=1900.0)
    
    # Check if we have any BREP files in the media directory
    media_dir = "media"
    if os.path.exists(media_dir):
        for file in os.listdir(media_dir):
            if file.endswith('.brep'):
                file_path = os.path.join(media_dir, file)
                print(f"Found BREP file: {file}")
                
                try:
                    # Try to add it as an internal cutout
                    panel.add_library_shape(
                        path=file_path,
                        kind="internal_cutout",
                        tx=400, ty=950, angle_deg=0, scale=1.0
                    )
                    print(f"Successfully added {file} as internal cutout")
                except Exception as e:
                    print(f"Failed to add {file}: {e}")
    
    return panel

if __name__ == "__main__":
    # Try to test with sample shapes first
    try:
        panel = test_with_sample_shapes()
        if panel.get_library_shapes_count()[0] > 0 or panel.get_library_shapes_count()[1] > 0:
            print("Testing with sample shapes...")
            main_with_panel(panel)
        else:
            print("No sample shapes found, testing base panel...")
            main()
    except Exception as e:
        print(f"Error with sample shapes: {e}")
        print("Testing base panel...")
        main()

def main_with_panel(panel):
    """Main function that takes a pre-configured panel."""
    print(f"Panel: {panel}")
    print(f"Dimensions: {panel.get_dimensions()}")
    edge_count, inner_count = panel.get_library_shapes_count()
    print(f"Library shapes: {edge_count} edge cuts, {inner_count} internal cuts")
    
    # Get the final shape
    print("Building shape...")
    shape = panel.as_shape()
    
    # Start the OCC viewer
    print("Starting OCC viewer...")
    display, start_display, add_menu, add_function_to_menu = init_display()
    
    # Display the shape
    print("Displaying shape...")
    display.DisplayShape(shape, color='lightblue', transparency=0.3, update=True)
    
    # Set 2D view (top view - XY plane)
    print("Setting 2D view...")
    display.View.SetProj(0, 0, 1)  # Top view (XY plane)
    display.FitAll()
    
    # Launch the interactive viewer loop
    print("Launching viewer... (close window to exit)")
    start_display()
