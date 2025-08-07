"""Utility functions for handling OCAF document generation."""

from pathlib import Path
from django.conf import settings

from upload_STEP.models import StepFile
from .models import OccDocument


def build_ocaf_document(step_file_path: str, out_path: str) -> None:
    """Generate an OCAF document from ``step_file_path`` and save to ``out_path``.

    This function relies on the :mod:`pythonocc-core` package. If it is not
    installed, a :class:`RuntimeError` is raised.
    """

    try:
        from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
        from OCC.Core.IFSelect import IFSelect_RetDone
        from OCC.Core.TDocStd import Handle_TDocStd_Document
        from OCC.Core.XCAFApp import XCAFApp_Application
        from OCC.Core.BinXCAFDrivers import BinXCAFDrivers
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("pythonocc-core is required to build an OCAF document") from exc

    app = XCAFApp_Application.GetApplication()
    BinXCAFDrivers.DefineFormat(app)
    doc = Handle_TDocStd_Document()
    app.NewDocument("BinXCAF", doc)

    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetLayerMode(True)
    reader.SetMaterialMode(True)

    status = reader.ReadFile(str(step_file_path))
    if status != IFSelect_RetDone:  # pragma: no cover - depends on external library
        raise RuntimeError("Failed to read STEP file")

    if not reader.Transfer(doc):  # pragma: no cover - depends on external library
        raise RuntimeError("Failed to transfer STEP data to OCAF document")

    app.SaveAs(doc, str(out_path))


def create_occ_document(step_file: StepFile) -> OccDocument:
    """Create an :class:`OccDocument` for the given STEP file."""

    output_dir = Path(settings.MEDIA_ROOT) / "occ_docs"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(step_file.file.name).stem + ".xb"
    out_path = output_dir / filename

    build_ocaf_document(step_file.file.path, out_path)

    relative_path = Path("occ_docs") / filename
    return OccDocument.objects.create(step_file=step_file, file=str(relative_path))

