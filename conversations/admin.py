from django.contrib import admin
from .models import Platform, Conversation, Message


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    """
    Platform Admin

    Manage connected messaging platforms (Email, WhatsApp, Instagram).
    Each user can connect one account per platform.
    """

    # Columns shown in the list view
    list_display = [
        'user',
        'platform_type',
        'is_active',
        'created_at',
    ]

    # Filters in the right sidebar
    list_filter = [
        'platform_type',
        'is_active',
        'created_at',
    ]

    # Fields you can search by
    search_fields = [
        'user__email',
        'user__company_name',
    ]

    # Default ordering
    ordering = ['-created_at']

    # Organize fields when editing
    fieldsets = (
        ('Connection', {
            'fields': ('user', 'platform_type', 'is_active')
        }),
        ('Credentials', {
            'fields': ('credentials',),
            'classes': ('collapse',),
            'description': 'API credentials for this platform (sensitive!)'
        }),
        ('Settings', {
            'fields': ('settings_data',),
            'classes': ('collapse',),
        }),
    )


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """
    Conversation Admin

    View and manage customer conversations.
    Each conversation groups messages with one customer.
    """

    # Columns shown in the list view
    list_display = [
        'customer_display',
        'platform',
        'user',
        'status',
        'needs_human_review',
        'message_count',
        'updated_at',
    ]

    # Filters in the right sidebar
    list_filter = [
        'platform',
        'status',
        'needs_human_review',
        'created_at',
        'user',
    ]

    # Fields you can search by
    search_fields = [
        'customer_name',
        'customer_email',
        'customer_phone',
        'customer_id',
        'user__email',
    ]

    # Default ordering
    ordering = ['-updated_at']

    # Read-only fields
    readonly_fields = ['customer_id', 'created_at', 'updated_at']

    # Organize fields when editing
    fieldsets = (
        ('Customer Info', {
            'fields': ('customer_id', 'customer_name', 'customer_email', 'customer_phone')
        }),
        ('Conversation', {
            'fields': ('user', 'platform', 'status', 'needs_human_review')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def customer_display(self, obj):
        """Show customer name or ID."""
        return obj.customer_name or f'ID: {obj.customer_id[:15]}...'
    customer_display.short_description = 'Customer'

    def message_count(self, obj):
        """Show number of messages in conversation."""
        return obj.get_message_count()
    message_count.short_description = 'Messages'


class MessageInline(admin.TabularInline):
    """
    Inline display of messages within a conversation.
    Shows messages directly on the conversation page.
    """
    model = Message
    extra = 0  # Don't show empty forms
    readonly_fields = ['direction', 'content', 'response_type', 'ai_confidence', 'created_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False  # Don't allow adding messages from admin


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Message Admin

    View individual messages in conversations.
    Tracks how each response was generated (AI, predefined, manual).
    """

    # Columns shown in the list view
    list_display = [
        'conversation',
        'direction',
        'content_preview',
        'response_type',
        'ai_confidence_display',
        'is_delivered',
        'created_at',
    ]

    # Filters in the right sidebar
    list_filter = [
        'direction',
        'response_type',
        'is_delivered',
        'created_at',
        'conversation__platform',
    ]

    # Fields you can search by
    search_fields = [
        'content',
        'conversation__customer_name',
        'conversation__user__email',
    ]

    # Default ordering
    ordering = ['-created_at']

    # Read-only fields
    readonly_fields = [
        'conversation',
        'direction',
        'response_type',
        'ai_confidence',
        'predefined_reply',
        'processing_time_ms',
        'created_at',
    ]

    # Organize fields when viewing
    fieldsets = (
        ('Message', {
            'fields': ('conversation', 'direction', 'content')
        }),
        ('Response Details', {
            'fields': ('response_type', 'ai_confidence', 'predefined_reply'),
            'classes': ('collapse',),
        }),
        ('Delivery', {
            'fields': ('is_delivered', 'error_message', 'processing_time_ms'),
            'classes': ('collapse',),
        }),
        ('Timestamp', {
            'fields': ('created_at',),
        }),
    )

    def content_preview(self, obj):
        """Show first 50 characters of message."""
        arrow = "← " if obj.direction == "inbound" else "→ "
        preview = obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
        return arrow + preview
    content_preview.short_description = 'Content'

    def ai_confidence_display(self, obj):
        """Show AI confidence as percentage."""
        if obj.ai_confidence:
            return f'{int(obj.ai_confidence * 100)}%'
        return '-'
    ai_confidence_display.short_description = 'AI Conf.'
