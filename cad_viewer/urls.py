from django.urls import path
from . import views

app_name = 'cad_viewer'

urlpatterns = [
    path('', views.cad_viewer, name='cad_viewer'),
    path('api/shapes/', views.get_shapes_library, name='get_shapes_library'),
    path('api/export-dxf/', views.export_to_dxf, name='export_to_dxf'),
    path('api/export-brep/', views.export_to_brep, name='export_to_brep'),
    path('api/export-pdf/', views.export_to_pdf, name='export_to_pdf'),
    path('api/render-brep/', views.render_brep_view, name='render_brep_view'),
]
