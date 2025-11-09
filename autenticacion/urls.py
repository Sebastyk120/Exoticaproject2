from django.urls import path
from . import views
from . import views_file_explorer

app_name = 'autenticacion'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.home_view, name='home'),
    path('password_reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password_reset/complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # File Explorer URLs
    path('file-explorer/', views_file_explorer.file_explorer_view, name='file_explorer'),
    path('file-explorer/<path:subpath>/', views_file_explorer.file_explorer_view, name='file_explorer_subpath'),
    path('file-download/<path:file_path>/', views_file_explorer.download_file, name='file_download'),
    path('file-delete/<path:file_path>/', views_file_explorer.delete_file, name='file_delete'),
]