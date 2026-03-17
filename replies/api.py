from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import PredefinedReply
from .serializers import PredefinedReplySerializer, PredefinedReplyListSerializer


class PredefinedReplyViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing predefined replies.

    list: Get all predefined replies for the current user
    create: Create a new predefined reply
    retrieve: Get a specific reply by ID
    update: Update a reply
    partial_update: Partially update a reply
    destroy: Delete a reply
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return PredefinedReplyListSerializer
        return PredefinedReplySerializer

    def get_queryset(self):
        """Only return replies belonging to the current user."""
        return PredefinedReply.objects.filter(
            user=self.request.user
        ).order_by('-created_at')

    def perform_create(self, serializer):
        """Set the user when creating a reply."""
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle the active status of a reply."""
        reply = self.get_object()
        reply.is_active = not reply.is_active
        reply.save()
        return Response({
            'id': reply.id,
            'is_active': reply.is_active,
            'message': f"Reply {'activated' if reply.is_active else 'deactivated'}"
        })

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get only active replies."""
        queryset = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def match(self, request):
        """
        Find matching replies for a given message.
        Useful for testing keyword matching.
        """
        message = request.data.get('message', '')
        if not message:
            return Response(
                {'error': 'Message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        matches = []
        for reply in self.get_queryset().filter(is_active=True):
            if reply.matches_message(message):
                matches.append({
                    'id': reply.id,
                    'name': reply.name,
                    'response': reply.response,
                    'matched_keywords': [
                        k for k in reply.keywords
                        if k.lower() in message.lower()
                    ]
                })

        return Response({
            'message': message,
            'matches': matches,
            'match_count': len(matches)
        })
