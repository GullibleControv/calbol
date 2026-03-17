from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Document, DocumentChunk
from .serializers import (
    DocumentSerializer,
    DocumentUploadSerializer,
    DocumentChunkSerializer
)


class DocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing knowledge base documents.

    list: Get all documents
    create: Upload a new document
    retrieve: Get document details
    destroy: Delete a document
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.action == 'create':
            return DocumentUploadSerializer
        return DocumentSerializer

    def get_queryset(self):
        """Only return documents belonging to the current user."""
        return Document.objects.filter(
            user=self.request.user
        ).order_by('-created_at')

    def perform_create(self, serializer):
        """Set the user when uploading a document."""
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        """Delete the file from storage when deleting document."""
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()

    @action(detail=True, methods=['get'])
    def chunks(self, request, pk=None):
        """Get all chunks for a document."""
        document = self.get_object()
        chunks = document.chunks.all()
        serializer = DocumentChunkSerializer(chunks, many=True)
        return Response({
            'document_id': document.id,
            'filename': document.filename,
            'chunk_count': chunks.count(),
            'chunks': serializer.data
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get document statistics for the current user."""
        queryset = self.get_queryset()
        total = queryset.count()
        processed = queryset.filter(processed=True).count()
        total_chunks = DocumentChunk.objects.filter(
            document__user=request.user
        ).count()

        return Response({
            'total_documents': total,
            'processed': processed,
            'pending': total - processed,
            'total_chunks': total_chunks
        })
