import os
import logging
from rest_framework import serializers
from .models import Document, DocumentChunk

logger = logging.getLogger(__name__)

# File validation constants
ALLOWED_EXTENSIONS = ['pdf', 'txt', 'docx', 'doc']
ALLOWED_MIME_TYPES = {
    'pdf': ['application/pdf'],
    'txt': ['text/plain'],
    'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    'doc': ['application/msword'],
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


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
        """
        Validate uploaded file with security checks.

        Security validations:
        1. Sanitize filename (prevent path traversal)
        2. Check file extension
        3. Verify MIME type
        4. Check file size
        """
        # 1. Sanitize filename
        filename = os.path.basename(value.name)
        value.name = filename

        # 2. Check file extension
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"Unsupported file type '.{ext}'. "
                f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # 3. Check file size
        if value.size > MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f"File size ({value.size / 1024 / 1024:.1f}MB) exceeds "
                f"maximum ({MAX_FILE_SIZE / 1024 / 1024:.0f}MB)."
            )

        # 4. Verify MIME type
        mime_type = self._detect_mime_type(value)
        allowed_mimes = ALLOWED_MIME_TYPES.get(ext, [])

        if mime_type and mime_type not in allowed_mimes:
            logger.warning(
                f"SECURITY: File MIME mismatch. Extension: {ext}, MIME: {mime_type}"
            )
            raise serializers.ValidationError(
                f"File content does not match extension '.{ext}'."
            )

        return value

    def _detect_mime_type(self, file) -> str:
        """
        Detect MIME type from file header using magic numbers.

        This provides basic MIME type detection for common file types
        to prevent extension spoofing attacks.
        """
        header = file.read(16)
        file.seek(0)

        # Windows/DOS executable (MZ header)
        if header.startswith(b'MZ'):
            return 'application/x-executable'

        # PDF signature
        if header.startswith(b'%PDF'):
            return 'application/pdf'

        # DOCX/Office Open XML signature (ZIP with specific content)
        if header.startswith(b'PK\x03\x04'):
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

        # DOC (older MS Word format)
        if header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
            return 'application/msword'

        # Plain text - check if first 512 bytes are valid UTF-8
        try:
            file.seek(0)
            sample = file.read(512)
            file.seek(0)
            sample.decode('utf-8')
            return 'text/plain'
        except (UnicodeDecodeError, AttributeError):
            logger.debug("File is not valid UTF-8 text")

        return ''

    def create(self, validated_data):
        file = validated_data['file']
        validated_data['filename'] = os.path.basename(file.name)
        validated_data['file_type'] = file.name.split('.')[-1].lower()
        return super().create(validated_data)
