from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from .models import Document, DocumentChunk
from .forms import DocumentUploadForm


@login_required
def document_list(request):
    """
    List all documents for the current user.
    Also handles file uploads via HTMX.
    """
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.user = request.user
            document.save()

            # Return updated document grid for HTMX
            documents = Document.objects.filter(user=request.user).order_by('-created_at')
            response = render(request, 'knowledge/partials/document_grid.html', {'documents': documents})
            response['HX-Trigger'] = 'closeModal'
            return response
        else:
            # Return form with errors
            return render(request, 'knowledge/partials/upload_form.html', {'form': form})

    documents = Document.objects.filter(user=request.user).order_by('-created_at')

    # If HTMX request, return just the grid
    if request.headers.get('HX-Request'):
        return render(request, 'knowledge/partials/document_grid.html', {'documents': documents})

    form = DocumentUploadForm()
    return render(request, 'knowledge/list.html', {'documents': documents, 'form': form})


@login_required
def document_upload_form(request):
    """Return the upload form modal."""
    form = DocumentUploadForm()
    return render(request, 'knowledge/partials/upload_form.html', {'form': form})


@login_required
@require_http_methods(["DELETE"])
def document_delete(request, pk):
    """Delete a document and its chunks."""
    document = get_object_or_404(Document, pk=pk, user=request.user)

    # Delete the file from storage
    if document.file:
        document.file.delete(save=False)

    document.delete()

    # Return updated grid
    documents = Document.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'knowledge/partials/document_grid.html', {'documents': documents})


@login_required
def document_detail(request, pk):
    """View document details and chunks."""
    document = get_object_or_404(Document, pk=pk, user=request.user)
    chunks = document.chunks.all()
    return render(request, 'knowledge/partials/document_detail.html', {
        'document': document,
        'chunks': chunks,
    })
