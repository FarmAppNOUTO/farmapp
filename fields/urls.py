from django.urls import path
from . import views

app_name = "fields"

urlpatterns = [
    path("", views.map_view, name="map"),
    path("save_option/", views.save_option, name="save_option"),
    path("delete_option/", views.delete_option, name="delete_option"),
    path("api/records/<int:field_id>/", views.get_records, name="get_records"),
    path("api/records/save/", views.save_record, name="save_record"),
    path("api/records/delete/", views.delete_record, name="delete_record"),
    path("api/records/sync/", views.sync_records, name="sync_records"),
    path("record/<int:field_id>/", views.record_view, name="record_form"),
]
