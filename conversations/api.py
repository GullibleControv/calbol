from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from .models import Platform, Conversation, Message
from .serializers import (
    PlatformSerializer,
    ConversationSerializer,
    ConversationDetailSerializer,
    MessageSerializer,
    SendMessageSerializer
)


class PlatformViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing connected platforms.
    """
    serializer_class = PlatformSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Platform.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle platform active status."""
        platform = self.get_object()
        platform.is_active = not platform.is_active
        platform.save()
        return Response({
            'id': platform.id,
            'is_active': platform.is_active
        })


class ConversationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing conversations.
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ConversationDetailSerializer
        return ConversationSerializer

    def get_queryset(self):
        queryset = Conversation.objects.filter(
            user=self.request.user
        ).order_by('-updated_at')

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by platform
        platform = self.request.query_params.get('platform')
        if platform:
            queryset = queryset.filter(platform=platform)

        # Filter by needs_human_review
        needs_review = self.request.query_params.get('needs_review')
        if needs_review == 'true':
            queryset = queryset.filter(needs_human_review=True)

        return queryset

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send a manual message in this conversation."""
        conversation = self.get_object()
        serializer = SendMessageSerializer(data=request.data)

        if serializer.is_valid():
            message = Message.objects.create(
                conversation=conversation,
                direction='outbound',
                content=serializer.validated_data['content'],
                response_type='manual'
            )
            return Response(
                MessageSerializer(message).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Mark conversation as resolved."""
        conversation = self.get_object()
        conversation.status = 'resolved'
        conversation.needs_human_review = False
        conversation.save()
        return Response({'status': 'resolved'})

    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        """Escalate conversation for human review."""
        conversation = self.get_object()
        conversation.status = 'escalated'
        conversation.needs_human_review = True
        conversation.save()
        return Response({'status': 'escalated'})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get conversation statistics."""
        queryset = Conversation.objects.filter(user=request.user)

        return Response({
            'total': queryset.count(),
            'active': queryset.filter(status='active').count(),
            'resolved': queryset.filter(status='resolved').count(),
            'escalated': queryset.filter(status='escalated').count(),
            'needs_review': queryset.filter(needs_human_review=True).count(),
            'by_platform': list(
                queryset.values('platform').annotate(count=Count('id'))
            )
        })


class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing messages (read-only).
    Messages are created through conversations.
    """
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Message.objects.filter(
            conversation__user=self.request.user
        ).order_by('-created_at')

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get most recent messages across all conversations."""
        limit = int(request.query_params.get('limit', 20))
        messages = self.get_queryset()[:limit]
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)


class AITestViewSet(viewsets.ViewSet):
    """
    API endpoints for testing AI functionality.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def test_response(self, request):
        """
        Test AI response generation without creating a conversation.

        POST /api/v1/ai/test_response/
        Body: {"message": "What are your prices?"}
        """
        from knowledge.services import RAGService

        message = request.data.get('message', '')
        if not message:
            return Response(
                {'error': 'Message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        rag = RAGService()
        result = rag.generate_response(
            user=request.user,
            message=message
        )

        return Response(result)

    @action(detail=False, methods=['post'])
    def simulate_message(self, request):
        """
        Simulate receiving a customer message.

        POST /api/v1/ai/simulate_message/
        Body: {
            "message": "What are your prices?",
            "customer_id": "test-customer-123",
            "platform": "whatsapp"
        }
        """
        from conversations.services import handle_incoming_message

        message = request.data.get('message', '')
        customer_id = request.data.get('customer_id', 'test-customer')
        platform = request.data.get('platform', 'test')

        if not message:
            return Response(
                {'error': 'Message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = handle_incoming_message(
            user_id=request.user.id,
            platform=platform,
            customer_id=customer_id,
            content=message,
            customer_name=request.data.get('customer_name', 'Test Customer')
        )

        return Response(result)

    @action(detail=False, methods=['get'])
    def search_knowledge(self, request):
        """
        Search the knowledge base for relevant content.

        GET /api/v1/ai/search_knowledge/?query=pricing
        """
        from knowledge.services import EmbeddingService

        query = request.query_params.get('query', '')
        if not query:
            return Response(
                {'error': 'Query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        embedding_service = EmbeddingService()
        results = embedding_service.search_user_knowledge(
            user=request.user,
            query=query,
            top_k=5
        )

        return Response({
            'query': query,
            'results': [
                {
                    'content': chunk['content'][:500],
                    'document': chunk['document_filename'],
                    'similarity': round(similarity, 3)
                }
                for chunk, similarity in results
            ]
        })
