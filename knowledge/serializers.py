from rest_framework import serializers
from .models import Document, DocumentChunk


class DocumentChunkSerializer(serializers.ModelSerializer):
    """Serializer for document chunks."""

    class Meta:
        model = DocumentChunk
        fields = ['id', 'chunk_index', 'content', 'char_count']
        read_only_fields = ['id', 'chunk_index', 'char_count']


class DocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for Document model.
    Includes chunk count for processed documents.
    """
    chunk_count = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id',
            'filename',
            'file',
            'file_url',
            'file_type',
            'description',
            'processed',
            'processing_error',
            'chunk_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'filename', 'file_type', 'processed',
            'processing_error', 'chunk_count', 'created_at', 'updated_at'
        ]

    def get_chunk_count(self, obj):
        return obj.get_chunk_count()

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None


class DocumentUploadSerializer(serializers.ModelSerializer):
    """Serializer for uploading documents."""

    class Meta:
        model = Document
        fields = ['file', 'description']

    def validate_file(self, value):
        # Check file extension
        ext = value.name.split('.')[-1].lower()
        allowed = ['pdf', 'txt', 'docx', 'doc']
        if ext not in allowed:
            raise serializers.ValidationError(
                f"Unsupported file type. Allowed: {', '.join(allowed)}"
            )

        # Check file size (10MB max)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size must be under 10MB.")

        return value

    def create(self, validated_data):
        file = validated_data['file']
        validated_data['filename'] = file.name
        validated_data['file_type'] = file.name.split('.')[-1].lower()
        return super().create(validated_data)
