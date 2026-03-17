from django.urls import path
from . import views

app_name = 'replies'

urlpatterns = [
    path('', views.reply_list, name='list'),
    path('create/', views.reply_create, name='create'),
    path('<int:pk>/edit/', views.reply_edit, name='edit'),
    path('<int:pk>/delete/', views.reply_delete, name='delete'),
    path('<int:pk>/toggle/', views.reply_toggle, name='toggle'),
]
