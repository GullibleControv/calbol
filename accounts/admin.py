from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom User Admin

    Extends Django's built-in UserAdmin to show our custom fields.
    This is what you see when you click "Users" in the admin panel.
    """

    # Columns shown in the user list
    list_display = [
        'email',
        'username',
        'company_name',
        'plan',
        'monthly_replies',
        'is_active',
        'date_joined',
    ]

    # Filters in the right sidebar
    list_filter = [
        'plan',
        'is_active',
        'is_staff',
        'date_joined',
    ]

    # Fields you can search by
    search_fields = [
        'email',
        'username',
        'company_name',
        'phone',
    ]

    # Default ordering
    ordering = ['-date_joined']

    # Organize fields into sections when editing a user
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'company_name', 'phone')}),
        ('Subscription', {'fields': ('plan', 'monthly_replies', 'monthly_ai_replies')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )

    # Fields shown when creating a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'company_name', 'plan'),
        }),
    )
