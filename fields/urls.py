from django.urls import path
from . import views

urlpatterns = [
    path('', views.map_view, name='map'),
    path('save_option/', views.save_option, name='save_option'),
    path('delete_option/', views.delete_option, name='delete_option'),  
]
