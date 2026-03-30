from django.urls import path
from django.contrib.auth import views as auth_views
from .views import CustomLoginView, RegisterView, logout_view

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('logout/', logout_view, name='logout'),

    # Password Reset URLs
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='auth/password_reset.html',
             email_template_name='auth/password_reset_email.html',
             subject_template_name='auth/password_reset_subject.txt',
             success_url='/auth/password-reset/done/'
         ),
         name='password_reset'),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='auth/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='auth/password_reset_confirm.html',
             success_url='/auth/password-reset-complete/'
         ),
         name='password_reset_confirm'),

    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='auth/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]
