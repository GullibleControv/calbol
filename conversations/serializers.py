from rest_framework import serializers
from .models import Platform, Conversation, Message


class PlatformSerializer(serializers.ModelSerializer):
    """Serializer for connected platforms."""
    platform_display = serializers.CharField(
        source='get_platform_type_display',
        read_only=True
    )

    class Meta:
        model = Platform
        fields = [
            'id',
            'platform_type',
            'platform_display',
            'is_active',
            'settings_data',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    # Don't expose credentials in API
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Never return credentials
        return data


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for individual messages."""
    response_type_display = serializers.CharField(
        source='get_response_type_display',
        read_only=True
    )

    class Meta:
        model = Message
        fields = [
            'id',
            'direction',
            'content',
            'response_type',
            'response_type_display',
            'ai_confidence',
            'is_delivered',
            'error_message',
            'processing_time_ms',
            'created_at',
        ]
        read_only_fields = [
            'id', 'response_type', 'ai_confidence',
            'processing_time_ms', 'created_at'
        ]


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for conversations with message count."""
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )

    class Meta:
        model = Conversation
        fields = [
            'id',
            'platform',
            'customer_id',
            'customer_name',
            'customer_email',
            'customer_phone',
            'status',
            'status_display',
            'needs_human_review',
            'message_count',
            'last_message',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'customer_id', 'created_at', 'updated_at']

    def get_message_count(self, obj):
        return obj.get_message_count()

    def get_last_message(self, obj):
        last = obj.get_last_message()
        if last:
            return {
                'content': last.content[:100],
                'direction': last.direction,
                'created_at': last.created_at,
            }
        return None


class ConversationDetailSerializer(ConversationSerializer):
    """Detailed serializer with all messages."""
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ['messages']


class SendMessageSerializer(serializers.Serializer):
    """Serializer for sending a manual message."""
    content = serializers.CharField(max_length=5000)

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Message cannot be empty.")
        return value.strip()
