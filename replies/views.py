from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from .models import PredefinedReply
from .forms import PredefinedReplyForm


@login_required
def reply_list(request):
    """
    List all predefined replies for the current user.
    Returns full page or partial based on HTMX request.
    """
    replies = PredefinedReply.objects.filter(user=request.user).order_by('-created_at')

    # If HTMX request, return just the table body
    if request.headers.get('HX-Request'):
        return render(request, 'replies/partials/reply_list.html', {'replies': replies})

    return render(request, 'replies/list.html', {'replies': replies})


@login_required
def reply_create(request):
    """
    Create a new predefined reply.
    Returns modal form or processes submission.
    """
    if request.method == 'POST':
        form = PredefinedReplyForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.user = request.user
            reply.save()

            # Return updated list for HTMX to swap
            replies = PredefinedReply.objects.filter(user=request.user).order_by('-created_at')
            response = render(request, 'replies/partials/reply_list.html', {'replies': replies})
            response['HX-Trigger'] = 'closeModal'
            return response
        else:
            # Return form with errors
            return render(request, 'replies/partials/reply_form.html', {
                'form': form,
                'action': 'create',
            })
    else:
        form = PredefinedReplyForm()

    return render(request, 'replies/partials/reply_form.html', {
        'form': form,
        'action': 'create',
    })


@login_required
def reply_edit(request, pk):
    """
    Edit an existing predefined reply.
    """
    reply = get_object_or_404(PredefinedReply, pk=pk, user=request.user)

    if request.method == 'POST':
        form = PredefinedReplyForm(request.POST, instance=reply)
        if form.is_valid():
            form.save()

            # Return updated list for HTMX to swap
            replies = PredefinedReply.objects.filter(user=request.user).order_by('-created_at')
            response = render(request, 'replies/partials/reply_list.html', {'replies': replies})
            response['HX-Trigger'] = 'closeModal'
            return response
        else:
            return render(request, 'replies/partials/reply_form.html', {
                'form': form,
                'reply': reply,
                'action': 'edit',
            })
    else:
        form = PredefinedReplyForm(instance=reply)

    return render(request, 'replies/partials/reply_form.html', {
        'form': form,
        'reply': reply,
        'action': 'edit',
    })


@login_required
@require_http_methods(["DELETE"])
def reply_delete(request, pk):
    """
    Delete a predefined reply.
    """
    reply = get_object_or_404(PredefinedReply, pk=pk, user=request.user)
    reply.delete()

    # Return updated list for HTMX to swap
    replies = PredefinedReply.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'replies/partials/reply_list.html', {'replies': replies})


@login_required
def reply_toggle(request, pk):
    """
    Toggle the active status of a reply.
    """
    reply = get_object_or_404(PredefinedReply, pk=pk, user=request.user)
    reply.is_active = not reply.is_active
    reply.save()

    # Return just the updated row
    return render(request, 'replies/partials/reply_row.html', {'reply': reply})
