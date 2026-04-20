from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('replies/', views.replies_list, name='replies'),
    path('documents/', views.documents_list, name='documents'),
    path('conversations/', views.conversations_list, name='conversations'),
    path('settings/', views.settings_page, name='settings'),
    path('analytics/', views.analytics_page, name='analytics'),
]
