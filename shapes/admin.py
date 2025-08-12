from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import ShapeAsset


@admin.register(ShapeAsset)
class ShapeAssetAdmin(admin.ModelAdmin):
    """Admin interface for ShapeAsset model."""
    
    list_display = [
        'name', 
        'is_processed', 
        'has_preview', 
        'get_bbox_display', 
        'get_area_display',
        'default_edge',
        'default_offset_mm',
        'created_at'
    ]
    
    list_filter = [
        'default_edge',
        'has_holes',
        'created_at',
        'updated_at'
    ]
    
    search_fields = ['name']
    
    readonly_fields = [
        'id',
        'bbox_w_mm',
        'bbox_h_mm', 
        'area_mm2',
        'has_holes',
        'is_processed',
        'has_preview',
        'created_at',
        'updated_at',
        'preview_display'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'source_brep', 'source_step')
        }),
        ('Processing Status', {
            'fields': ('is_processed', 'has_preview', 'preview_display'),
            'classes': ('collapse',)
        }),
        ('Derived Properties (Read-only)', {
            'fields': ('bbox_w_mm', 'bbox_h_mm', 'area_mm2', 'has_holes'),
            'classes': ('collapse',)
        }),
        ('Placement Defaults', {
            'fields': ('default_edge', 'default_offset_mm'),
            'description': 'Default placement settings for this shape'
        }),
        ('Attach Frame Parameters', {
            'fields': ('attach_x_mm', 'attach_y_mm', 'attach_angle_deg'),
            'description': 'Local coordinate system for shape attachment'
        }),
        ('Generated Files', {
            'fields': ('canonical_brep', 'preview_svg'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['regenerate_derived_properties', 'delete_selected_with_files']
    
    def preview_display(self, obj):
        """Display the preview SVG if available."""
        if obj.preview_svg:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 150px;" />',
                obj.preview_svg.url
            )
        return "No preview available"
    preview_display.short_description = "Preview"
    
    def is_processed(self, obj):
        """Display processing status."""
        return obj.is_processed
    is_processed.boolean = True
    is_processed.short_description = "Processed"
    
    def has_preview(self, obj):
        """Display preview availability."""
        return obj.has_preview
    has_preview.boolean = True
    has_preview.short_description = "Has Preview"
    
    def get_bbox_display(self, obj):
        """Display bounding box dimensions."""
        return obj.get_bbox_display()
    get_bbox_display.short_description = "Bounding Box"
    
    def get_area_display(self, obj):
        """Display area."""
        return obj.get_area_display()
    get_area_display.short_description = "Area"
    
    def regenerate_derived_properties(self, request, queryset):
        """Admin action to regenerate derived properties."""
        count = 0
        for shape in queryset:
            try:
                from .services import process_shape_asset
                process_shape_asset(shape)
                count += 1
            except Exception as e:
                self.message_user(
                    request, 
                    f"Error processing {shape.name}: {str(e)}", 
                    level='ERROR'
                )
        
        self.message_user(
            request,
            f"Successfully regenerated properties for {count} shape(s)."
        )

    def delete_selected_with_files(self, request, queryset):
        """Delete selected shapes and their associated files."""
        count = 0
        for shape in queryset:
            try:
                # This will call our custom delete method that cleans up files
                shape.delete()
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error deleting {shape.name}: {str(e)}",
                    level='ERROR'
                )
        
        self.message_user(
            request,
            f"Successfully deleted {count} shape(s) and their associated files."
        )
    
    delete_selected_with_files.short_description = "Delete selected shapes and files"
    regenerate_derived_properties.short_description = "Regenerate derived properties"
    
    def save_model(self, request, obj, form, change):
        """Override save to trigger import pipeline on new uploads."""
        is_new = obj.pk is None
        super().save_model(request, obj, form, change)
        
        # If this is a new upload, trigger the import pipeline
        if is_new and (obj.source_brep or obj.source_step):
            try:
                from .services import process_shape_asset
                print(f"Starting to process shape: {obj.name}")
                process_shape_asset(obj)
                print(f"Successfully processed shape: {obj.name}")
                self.message_user(
                    request, 
                    f"Shape '{obj.name}' uploaded and processed successfully!",
                    level='SUCCESS'
                )
            except Exception as e:
                import traceback
                print(f"Error processing shape {obj.name}: {e}")
                print("Full traceback:")
                print(traceback.format_exc())
                self.message_user(
                    request, 
                    f"Error processing shape '{obj.name}': {str(e)}",
                    level='ERROR'
                )
