from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.views.generic import CreateView
from django.urls import reverse_lazy
from .forms import LoginForm, RegisterForm


def landing_page(request):
    """Public landing page — shown at root URL instead of redirecting to login."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return render(request, 'public/landing.html')


class CustomLoginView(LoginView):
    """
    Login page for CalBol.
    Redirects to dashboard after successful login.
    """
    form_class = LoginForm
    template_name = 'auth/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('dashboard:home')


class RegisterView(CreateView):
    """
    Registration page for new users.
    Creates account and logs user in automatically.
    """
    form_class = RegisterForm
    template_name = 'auth/register.html'
    success_url = reverse_lazy('dashboard:home')

    def dispatch(self, request, *args, **kwargs):
        # Redirect to dashboard if already logged in
        if request.user.is_authenticated:
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Save the user
        response = super().form_valid(form)
        # Log the user in automatically
        login(self.request, self.object)
        return response


def logout_view(request):
    """Log out and redirect to home page."""
    logout(request)
    return redirect('accounts:login')
