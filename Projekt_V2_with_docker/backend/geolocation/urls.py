from django.urls import path
from . import views

app_name = 'geolocation'

urlpatterns = [
    path('select/', views.select_location, name='select_location'),
    path('api/get_address/', views.get_address_api, name='get_address_api'),
    path('api/save_location/', views.save_location, name='save_location'),
    path('history/', views.location_history, name='location_history'),
]
