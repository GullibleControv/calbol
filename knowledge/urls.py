from django.urls import path
from . import views

app_name = 'knowledge'

urlpatterns = [
    path('', views.document_list, name='list'),
    path('upload/', views.document_upload_form, name='upload_form'),
    path('<int:pk>/', views.document_detail, name='detail'),
    path('<int:pk>/delete/', views.document_delete, name='delete'),
]
