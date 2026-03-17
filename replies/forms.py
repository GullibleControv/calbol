from django import forms
from .models import PredefinedReply


class PredefinedReplyForm(forms.ModelForm):
    """
    Form for creating and editing predefined replies.
    Keywords are entered as comma-separated text and converted to a list.
    """

    # Override keywords to accept comma-separated text input
    keywords_text = forms.CharField(
        label='Keywords',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            'placeholder': 'price, cost, how much, pricing',
        }),
        help_text='Enter keywords separated by commas'
    )

    class Meta:
        model = PredefinedReply
        fields = ['name', 'response', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent',
                'placeholder': 'e.g., Pricing Question',
            }),
            'response': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent',
                'rows': 4,
                'placeholder': 'The response to send when keywords are detected...',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If editing, convert keywords list to comma-separated string
        if self.instance and self.instance.pk:
            self.fields['keywords_text'].initial = ', '.join(self.instance.keywords or [])

    def clean_keywords_text(self):
        """Convert comma-separated text to a list of keywords."""
        keywords_text = self.cleaned_data.get('keywords_text', '')
        # Split by comma, strip whitespace, remove empty strings, lowercase
        keywords = [k.strip().lower() for k in keywords_text.split(',') if k.strip()]
        if not keywords:
            raise forms.ValidationError('Please enter at least one keyword.')
        return keywords

    def save(self, commit=True):
        """Save the form and set keywords from keywords_text."""
        instance = super().save(commit=False)
        instance.keywords = self.cleaned_data['keywords_text']
        if commit:
            instance.save()
        return instance
