# CPQ4

A Django-based CAD file processing application for converting FreeCAD FCStd files to OCAF (OpenCASCADE Application Framework) documents.

## Features

- Upload and store FreeCAD FCStd files (`.FCStd`)
- Convert FCStd files to OCAF documents using native OpenCASCADE
- Parse FCStd as ZIP archive to extract Document.xml and BREP files
- Admin interface for file management and conversion
- File validation and error handling
- Fallback functionality when OpenCASCADE is not available

## How It Works

The application treats FCStd files as ZIP archives and:

1. **Extracts Document.xml** - Contains the OCAF label tree with part information
2. **Parses XML structure** - Identifies parts, names, and BREP file references
3. **Reads BREP files** - Converts serialized TopoDS_Shape data to OCC shapes
4. **Rebuilds OCAF document** - Creates new OCAF document with proper hierarchy
5. **Preserves metadata** - Maintains part names, relationships, and attributes

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. **Install OpenCASCADE (Required for real conversion):**
```bash
# Option 1: Using conda (recommended)
conda install -c conda-forge occt

# Option 2: Using pip
pip install OCC-Core==7.7.0

# Option 3: Using conda-forge
conda install -c conda-forge pythonocc-core
```

3. Run migrations:
```bash
python manage.py migrate
```

4. Create a superuser:
```bash
python manage.py createsuperuser
```

5. Run the development server:
```bash
python manage.py runserver
```

## Usage

1. Access the admin interface at `/admin/`
2. Upload FCStd files through the "FCStd files" section
3. Select a FCStd file and use the "Generate OCAF" action to convert it
4. Generated OCAF documents will be stored in the "OCAF documents" section

## Dependencies

- Django 5.2.5
- OCC-Core 7.7.0 (OpenCASCADE Python bindings) - **Optional but recommended**

## Technical Details

### FCStd Structure
- **Document.xml**: OCAF label tree with part hierarchy
- **BREP files**: Serialized TopoDS_Shape data in Shapes/Breps folders
- **ZIP format**: FCStd is essentially a ZIP archive

### Conversion Process
1. **ZIP extraction**: Opens FCStd as ZIP archive
2. **XML parsing**: Extracts part information from Document.xml
3. **BREP reading**: Converts BREP data to TopoDS_Shape objects
4. **OCAF creation**: Builds new OCAF document with XDE tools
5. **Metadata preservation**: Maintains part names and relationships

## Troubleshooting

### OpenCASCADE Installation Issues

If you encounter OpenCASCADE-related errors:

1. **Check if OpenCASCADE is installed:**
```bash
python -c "import OCC; print('OpenCASCADE available')"
```

2. **Install using conda (recommended):**
```bash
conda install -c conda-forge occt
```

3. **Alternative installation methods:**
```bash
# Using conda-forge
conda install -c conda-forge pythonocc-core

# Using pip (may have compatibility issues)
pip install OCC-Core==7.7.0
```

### Fallback Mode

If OpenCASCADE is not installed, the application will:
- Create mock OCAF files for testing
- Display a warning message
- Allow the admin interface to work without real conversion
- Show parsed part information in the mock file

This enables development and testing without requiring OpenCASCADE installation.