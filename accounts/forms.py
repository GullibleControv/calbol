from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils.translation import gettext_lazy as _
from .models import User


class UserSettingsForm(forms.ModelForm):
    """
    Form for updating user account settings.
    Allows users to update their company name and phone number.
    """
    company_name = forms.CharField(
        label=_('Company Name'),
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-surface-200 rounded-2xl focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all input-animated',
            'placeholder': _('Your company name'),
        })
    )
    phone = forms.CharField(
        label=_('Phone Number'),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-surface-200 rounded-2xl focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all input-animated',
            'placeholder': _('+1 234 567 8900'),
        })
    )

    class Meta:
        model = User
        fields = ['company_name', 'phone']


class LoginForm(AuthenticationForm):
    """
    Custom login form.
    Uses email as the username field (matches our User model).
    """
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'you@company.com',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '••••••••',
        })
    )


class RegisterForm(UserCreationForm):
    """
    Registration form for new users.
    Collects email, company name, and password.
    """
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'you@company.com',
        })
    )
    company_name = forms.CharField(
        label='Company Name',
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Your Business Name',
        })
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '••••••••',
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '••••••••',
        })
    )

    class Meta:
        model = User
        fields = ['email', 'company_name', 'password1', 'password2']

    def save(self, commit=True):
        """Save user with email as username."""
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']  # Use email as username
        user.email = self.cleaned_data['email']
        user.company_name = self.cleaned_data.get('company_name', '')
        if commit:
            user.save()
        return user
