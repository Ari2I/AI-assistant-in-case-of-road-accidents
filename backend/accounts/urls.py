from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('api/user-data/', views.user_data_api, name='user_data_api'),
    path('api/save-europrotocol/', views.save_europrotocol, name='save_europrotocol'),
]
