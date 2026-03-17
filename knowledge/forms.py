from django import forms
from .models import Document


class DocumentUploadForm(forms.ModelForm):
    """
    Form for uploading documents to the knowledge base.
    Accepts PDF, TXT, and DOCX files.
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
        """Validate file type and size."""
        file = self.cleaned_data.get('file')
        if file:
            # Check file extension
            ext = file.name.split('.')[-1].lower()
            allowed_extensions = ['pdf', 'txt', 'docx', 'doc']
            if ext not in allowed_extensions:
                raise forms.ValidationError(
                    f'Unsupported file type. Allowed: {", ".join(allowed_extensions)}'
                )

            # Check file size (max 10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if file.size > max_size:
                raise forms.ValidationError('File size must be under 10MB.')

        return file

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
