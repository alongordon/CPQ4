"""Services for OCC-based document operations."""
from __future__ import annotations

import os
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from django.conf import settings

from .models import OccDocument
from upload_FCStd.models import FCStdUpload


def parse_fcstd_document(fcstd_path: str | Path) -> dict:
    """Parse the Document.xml from an FCStd file to extract part information.
    
    Parameters
    ----------
    fcstd_path: Path-like
        Path to the FCStd file
        
    Returns
    -------
    dict
        Dictionary containing part information with names, BREP file paths, and hierarchy
    """
    fcstd_path = Path(fcstd_path)
    
    with zipfile.ZipFile(fcstd_path, 'r') as zip_file:
        # Read Document.xml
        if 'Document.xml' not in zip_file.namelist():
            raise ValueError("Document.xml not found in FCStd file")
        
        xml_content = zip_file.read('Document.xml')
        root = ET.fromstring(xml_content)
        
        # Parse the XML to extract part information
        parts = {}
        
        # Look for Object elements that represent parts
        for obj in root.findall('.//Object'):
            obj_id = obj.get('id')
            name_elem = obj.find('.//Property[@name="Label"]/String')
            if name_elem is not None:
                name = name_elem.get('value', f"Part_{obj_id}")
                
                # Look for BREP file reference
                brep_elem = obj.find('.//Property[@name="Shape"]/Part')
                if brep_elem is not None:
                    brep_file = brep_elem.get('file', '')
                    if brep_file:
                        parts[obj_id] = {
                            'name': name,
                            'brep_file': brep_file,
                            'id': obj_id
                        }
        
        return parts


def read_brep_shape(zip_file: zipfile.ZipFile, brep_file_path: str):
    """Read a BREP file from the FCStd ZIP and convert to OCC shape.
    
    Parameters
    ----------
    zip_file: zipfile.ZipFile
        Open ZIP file containing the FCStd contents
    brep_file_path: str
        Path to the BREP file within the ZIP
        
    Returns
    -------
    TopoDS_Shape or None
        The OCC shape if successful, None if failed
    """
    try:
        # Read BREP file from ZIP
        brep_data = zip_file.read(brep_file_path)
        
        # Try to import OpenCASCADE
        try:
            from OCC.Core.BRepTools import BRepTools
            from OCC.Core.TopoDS import TopoDS_Shape
            from OCC.Core.BRep import BRep_Builder
            from OCC.Core.TopoDS import TopoDS_Compound
            from io import BytesIO
            
            # Create a compound to hold the shape
            compound = TopoDS_Compound()
            builder = BRep_Builder()
            builder.MakeCompound(compound)
            
            # Read the BREP data
            shape = TopoDS_Shape()
            brep_stream = BytesIO(brep_data)
            
            # Try to read the BREP data
            if BRepTools.Read(shape, brep_stream):
                return shape
            else:
                print(f"Failed to read BREP file: {brep_file_path}")
                return None
                
        except ImportError:
            print("OpenCASCADE not available. Creating mock shape data.")
            return f"Mock shape from {brep_file_path}"
            
    except Exception as e:
        print(f"Error reading BREP file {brep_file_path}: {e}")
        return None


def build_ocaf_from_fcstd(fcstd_path: str | Path, ocaf_path: str | Path) -> None:
    """Convert an FCStd file to an OCAF document.
    
    Parameters
    ----------
    fcstd_path: Path-like
        Path to the input FCStd file
    ocaf_path: Path-like
        Path for the output OCAF document
    """
    fcstd_path = Path(fcstd_path)
    ocaf_path = Path(ocaf_path)
    
    try:
        # Parse the FCStd document
        parts = parse_fcstd_document(fcstd_path)
        
        # Try to use OpenCASCADE for real conversion
        try:
            from OCC.Core.TDocStd import TDocStd_Document
            from OCC.Core.TDF import TDF_Label
            from OCC.Core.TCollection import TCollection_ExtendedString
            from OCC.Core.XCAFDoc import XCAFDoc_ShapeTool
            from OCC.Core.BinXCAFDrivers import binxcafdrivers_DefineFormat
            from OCC.Core.XCAFApp import XCAFApp_Application
            
            # Create OCAF application and document
            app = XCAFApp_Application.GetApplication()
            binxcafdrivers_DefineFormat(app)
            
            format_name = TCollection_ExtendedString("BinXCAF")
            doc_handle = app.NewDocument(format_name)
            
            # Get the root label
            root_label = doc_handle.Main()
            
            # Create shape tool for adding shapes
            shape_tool = XCAFDoc_ShapeTool(root_label)
            
            # Process each part
            with zipfile.ZipFile(fcstd_path, 'r') as zip_file:
                for part_id, part_info in parts.items():
                    shape = read_brep_shape(zip_file, part_info['brep_file'])
                    if shape and hasattr(shape, 'IsNull') and not shape.IsNull():
                        # Create new label for this part
                        part_label = shape_tool.NewShapeLabel(root_label)
                        shape_tool.SetShape(part_label, shape)
                        shape_tool.SetName(part_label, TCollection_ExtendedString(part_info['name']))
            
            # Save the OCAF document
            app.SaveAs(doc_handle, str(ocaf_path))
            
        except ImportError:
            # Fallback: Create a mock OCAF file
            print("OpenCASCADE not available. Creating mock OCAF file.")
            with open(ocaf_path, 'w') as f:
                f.write(f"Mock OCAF document created from {fcstd_path}\n")
                f.write("This is a placeholder file. Install OpenCASCADE for real conversion.\n")
                f.write(f"Found {len(parts)} parts in the FCStd file:\n")
                for part_id, part_info in parts.items():
                    f.write(f"- {part_info['name']} (ID: {part_id}, BREP: {part_info['brep_file']})\n")
                    
    except Exception as e:
        raise RuntimeError(f"Failed to convert FCStd to OCAF: {e}")


def create_ocaf_from_fcstd(fcstd_file: FCStdUpload) -> OccDocument:
    """Create an OCAF document from an FCStd file.
    
    Parameters
    ----------
    fcstd_file: FCStdUpload
        The FCStdUpload instance to process
        
    Returns
    -------
    OccDocument
        The created OCAF document instance
        
    Raises
    ------
    RuntimeError
        If the FCStd file cannot be processed
    """
    # Generate output filename based on input filename
    fcstd_filename = os.path.splitext(os.path.basename(fcstd_file.file.name))[0]
    ocaf_filename = f"{fcstd_filename}.occ"
    
    # Define paths
    fcstd_path = fcstd_file.file.path
    ocaf_path = os.path.join(settings.MEDIA_ROOT, "occ_docs", ocaf_filename)
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(ocaf_path), exist_ok=True)
    
    # Generate the OCAF document
    build_ocaf_from_fcstd(fcstd_path, ocaf_path)
    
    # Create and save the OccDocument instance
    occ_document = OccDocument(
        fcstd_file=fcstd_file,
        file=f"occ_docs/{ocaf_filename}"
    )
    occ_document.save()
    
    return occ_document
