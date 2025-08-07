"""Services for OCC-based document operations."""
from __future__ import annotations

from pathlib import Path

from OCC.Core.BinXCAFDrivers import binxcafdrivers_DefineFormat
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.XCAFApp import XCAFApp_Application


def build_ocaf_document(step_path: str | Path, ocaf_path: str | Path) -> None:
    """Generate an OCAF document from a STEP file.

    Parameters
    ----------
    step_path: Path-like
        Location of the input STEP file.
    ocaf_path: Path-like
        Destination path for the generated OCAF document.

    The function uses the BinXCAF format drivers to create a new document
    and transfers the STEP contents into it before saving.
    """
    step_path = Path(step_path)
    ocaf_path = Path(ocaf_path)

    app = XCAFApp_Application.GetApplication()
    binxcafdrivers_DefineFormat(app)

    # Create the document handle using the newer API which directly returns it
    doc = app.NewDocument("BinXCAF")

    reader = STEPCAFControl_Reader()
    status = reader.ReadFile(str(step_path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"Failed to read STEP file: {step_path}")

    reader.Transfer(doc)
    app.SaveAs(doc, str(ocaf_path))
