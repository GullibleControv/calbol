from django.contrib import admin
from .models import Document, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """
    Document Admin

    Manage uploaded knowledge base documents.
    Documents are processed into chunks for AI search.
    """

    # Columns shown in the list view
    list_display = [
        'filename',
        'user',
        'file_type',
        'processed',
        'chunk_count',
        'created_at',
    ]

    # Filters in the right sidebar
    list_filter = [
        'processed',
        'file_type',
        'created_at',
        'user',
    ]

    # Fields you can search by
    search_fields = [
        'filename',
        'description',
        'user__email',
    ]

    # Default ordering
    ordering = ['-created_at']

    # Read-only fields
    readonly_fields = ['processed', 'processing_error', 'created_at', 'updated_at']

    # Organize fields when editing
    fieldsets = (
        ('Document Info', {
            'fields': ('user', 'filename', 'file', 'file_type', 'description')
        }),
        ('Processing Status', {
            'fields': ('processed', 'processing_error'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def chunk_count(self, obj):
        """Show number of chunks this document has."""
        count = obj.get_chunk_count()
        return f'{count} chunks' if count else 'Not processed'
    chunk_count.short_description = 'Chunks'


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    """
    Document Chunk Admin

    View individual chunks of processed documents.
    Each chunk can be searched by AI for relevant context.
    """

    # Columns shown in the list view
    list_display = [
        'document',
        'chunk_index',
        'content_preview',
        'char_count',
        'has_embedding_display',
    ]

    # Filters in the right sidebar
    list_filter = [
        'document__file_type',
        'document__user',
    ]

    # Fields you can search by
    search_fields = [
        'content',
        'document__filename',
    ]

    # Default ordering
    ordering = ['document', 'chunk_index']

    # Read-only fields
    readonly_fields = ['char_count', 'embedding']

    def content_preview(self, obj):
        """Show first 100 characters of content."""
        if len(obj.content) > 100:
            return obj.content[:100] + '...'
        return obj.content
    content_preview.short_description = 'Content Preview'

    def has_embedding_display(self, obj):
        """Show whether chunk has been embedded."""
        return '✓' if obj.has_embedding() else '✗'
    has_embedding_display.short_description = 'Embedded'
