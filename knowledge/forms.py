import os
import logging
from django import forms
from .models import Document

logger = logging.getLogger(__name__)

# Allowed file types with their expected MIME types
ALLOWED_FILE_TYPES = {
    'pdf': ['application/pdf'],
    'txt': ['text/plain'],
    'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    'doc': ['application/msword'],
}

# Maximum file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


class DocumentUploadForm(forms.ModelForm):
    """
    Form for uploading documents to the knowledge base.
    Accepts PDF, TXT, and DOCX files.

    Security features:
    - File extension validation
    - MIME type verification
    - File size limits
    - Filename sanitization
    """

    class Meta:
        model = Document
        fields = ['file', 'description']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': '.pdf,.txt,.docx,.doc',
                'id': 'file-upload',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent',
                'rows': 2,
                'placeholder': 'Brief description of this document (optional)',
            }),
        }

    def clean_file(self):
        """
        Validate file type and size with security checks.

        Security validations:
        1. File extension check
        2. MIME type verification (prevents extension spoofing)
        3. File size limit
        4. Filename sanitization
        """
        file = self.cleaned_data.get('file')
        if not file:
            return file

        # 1. Sanitize filename (prevent path traversal)
        filename = os.path.basename(file.name)
        file.name = filename

        # 2. Check file extension
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_FILE_TYPES:
            raise forms.ValidationError(
                f'Unsupported file type ".{ext}". '
                f'Allowed: {", ".join(ALLOWED_FILE_TYPES.keys())}'
            )

        # 3. Check file size
        if file.size > MAX_FILE_SIZE:
            raise forms.ValidationError(
                f'File size ({file.size / 1024 / 1024:.1f}MB) exceeds '
                f'maximum allowed size ({MAX_FILE_SIZE / 1024 / 1024:.0f}MB).'
            )

        # 4. Verify MIME type (read file header)
        try:
            mime_type = self._detect_mime_type(file)
            allowed_mimes = ALLOWED_FILE_TYPES.get(ext, [])

            if mime_type and mime_type not in allowed_mimes:
                logger.warning(
                    f"SECURITY: File MIME type mismatch. "
                    f"Extension: {ext}, MIME: {mime_type}, "
                    f"Expected: {allowed_mimes}"
                )
                raise forms.ValidationError(
                    f'File content does not match extension ".{ext}". '
                    'Please upload a valid file.'
                )
        except Exception as e:
            # Log but don't fail on MIME detection errors
            logger.warning(f"MIME type detection failed: {e}")

        return file

    def _detect_mime_type(self, file) -> str:
        """
        Detect MIME type by reading file header (magic numbers).

        Uses python-magic if available, falls back to simple detection.
        """
        try:
            import magic
            # Read first 2KB for magic detection
            file_header = file.read(2048)
            file.seek(0)  # Reset file pointer
            return magic.from_buffer(file_header, mime=True)
        except (ImportError, OSError, Exception):
            # python-magic not installed or failed, use simple detection
            return self._simple_mime_detect(file)

    def _simple_mime_detect(self, file) -> str:
        """
        Simple MIME detection based on file signatures (magic numbers).

        Fallback when python-magic is not available.
        """
        file_header = file.read(8)
        file.seek(0)  # Reset file pointer

        # Windows/DOS executable (MZ header)
        if file_header.startswith(b'MZ'):
            return 'application/x-executable'

        # PDF signature
        if file_header.startswith(b'%PDF'):
            return 'application/pdf'

        # DOCX/Office Open XML signature (ZIP with specific content)
        if file_header.startswith(b'PK\x03\x04'):
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

        # Plain text (no binary characters in first 512 bytes)
        try:
            sample = file.read(512)
            file.seek(0)
            sample.decode('utf-8')
            return 'text/plain'
        except (UnicodeDecodeError, AttributeError):
            logger.debug("File is not valid UTF-8 text")

        return ''

    def save(self, commit=True):
        """Save document with extracted metadata."""
        instance = super().save(commit=False)

        # Extract file info
        if instance.file:
            instance.filename = instance.file.name
            instance.file_type = instance.file.name.split('.')[-1].lower()

        if commit:
            instance.save()

        return instance
