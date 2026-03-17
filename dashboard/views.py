from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from conversations.models import Conversation, Message
from replies.models import PredefinedReply
from knowledge.models import Document


@login_required
def home(request):
    """
    Dashboard home page.
    Shows overview stats and recent activity.
    """
    user = request.user

    # Get statistics
    stats = {
        'total_conversations': Conversation.objects.filter(user=user).count(),
        'active_conversations': Conversation.objects.filter(user=user, status='active').count(),
        'needs_review': Conversation.objects.filter(user=user, needs_human_review=True).count(),
        'total_messages': Message.objects.filter(conversation__user=user).count(),
        'ai_replies': Message.objects.filter(
            conversation__user=user,
            direction='outbound',
            response_type='ai'
        ).count(),
        'predefined_replies': PredefinedReply.objects.filter(user=user, is_active=True).count(),
        'documents': Document.objects.filter(user=user).count(),
        'monthly_usage': user.monthly_replies,
        'monthly_limit': user.get_plan_limit(),
    }

    # Calculate usage percentage
    if stats['monthly_limit'] == float('inf'):
        stats['usage_percent'] = 0
    else:
        stats['usage_percent'] = int((stats['monthly_usage'] / stats['monthly_limit']) * 100)

    # Get recent conversations
    recent_conversations = Conversation.objects.filter(user=user).order_by('-updated_at')[:5]

    # Get recent messages that need attention
    flagged_conversations = Conversation.objects.filter(
        user=user,
        needs_human_review=True
    ).order_by('-updated_at')[:5]

    context = {
        'stats': stats,
        'recent_conversations': recent_conversations,
        'flagged_conversations': flagged_conversations,
    }

    return render(request, 'dashboard/home.html', context)


@login_required
def replies_list(request):
    """
    List all predefined replies.
    """
    replies = PredefinedReply.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'dashboard/replies.html', {'replies': replies})


@login_required
def documents_list(request):
    """
    List all uploaded documents.
    """
    documents = Document.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'dashboard/documents.html', {'documents': documents})


@login_required
def conversations_list(request):
    """
    List all conversations.
    """
    conversations = Conversation.objects.filter(user=request.user).order_by('-updated_at')
    return render(request, 'dashboard/conversations.html', {'conversations': conversations})


@login_required
def settings_page(request):
    """
    User settings page.
    """
    return render(request, 'dashboard/settings.html')
