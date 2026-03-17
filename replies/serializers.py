from rest_framework import serializers
from .models import PredefinedReply


class PredefinedReplySerializer(serializers.ModelSerializer):
    """
    Serializer for PredefinedReply model.
    Used for API CRUD operations.
    """
    # Show keywords as a list in API
    keywords = serializers.ListField(
        child=serializers.CharField(max_length=100),
        help_text="List of trigger keywords"
    )

    class Meta:
        model = PredefinedReply
        fields = [
            'id',
            'name',
            'keywords',
            'response',
            'is_active',
            'use_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'use_count', 'created_at', 'updated_at']

    def validate_keywords(self, value):
        """Ensure keywords are lowercase and unique."""
        keywords = [k.lower().strip() for k in value if k.strip()]
        if not keywords:
            raise serializers.ValidationError("At least one keyword is required.")
        return list(set(keywords))  # Remove duplicates


class PredefinedReplyListSerializer(serializers.ModelSerializer):
    """
    Lighter serializer for listing replies.
    """
    keyword_count = serializers.SerializerMethodField()

    class Meta:
        model = PredefinedReply
        fields = ['id', 'name', 'keyword_count', 'is_active', 'use_count']

    def get_keyword_count(self, obj):
        return len(obj.keywords) if obj.keywords else 0
