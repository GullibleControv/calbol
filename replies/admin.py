from django.contrib import admin
from .models import PredefinedReply


@admin.register(PredefinedReply)
class PredefinedReplyAdmin(admin.ModelAdmin):
    """
    Predefined Reply Admin

    Manage FAQ-style automatic replies.
    Business owners create these to answer common questions instantly.
    """

    # Columns shown in the list view
    list_display = [
        'name',
        'user',
        'keywords_preview',
        'is_active',
        'use_count',
        'created_at',
    ]

    # Filters in the right sidebar
    list_filter = [
        'is_active',
        'created_at',
        'user',
    ]

    # Fields you can search by
    search_fields = [
        'name',
        'keywords',
        'response',
        'user__email',
    ]

    # Default ordering
    ordering = ['-created_at']

    # Read-only fields (can't be edited)
    readonly_fields = ['use_count', 'created_at', 'updated_at']

    # Organize fields when editing
    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'name', 'is_active')
        }),
        ('Trigger & Response', {
            'fields': ('keywords', 'response'),
            'description': 'Keywords trigger this reply. Response is sent to the customer.'
        }),
        ('Statistics', {
            'fields': ('use_count', 'created_at', 'updated_at'),
            'classes': ('collapse',),  # Collapsible section
        }),
    )

    def keywords_preview(self, obj):
        """Show first 3 keywords in the list view."""
        if obj.keywords:
            preview = ', '.join(obj.keywords[:3])
            if len(obj.keywords) > 3:
                preview += f' (+{len(obj.keywords) - 3} more)'
            return preview
        return '-'
    keywords_preview.short_description = 'Keywords'
