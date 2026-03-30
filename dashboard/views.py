import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _
from conversations.models import Conversation, Message
from replies.models import PredefinedReply
from knowledge.models import Document
from analytics.services import AnalyticsService, DateRange
from accounts.forms import UserSettingsForm


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
    Handles viewing and updating account settings.
    """
    if request.method == 'POST':
        form = UserSettingsForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _('Settings saved successfully!'))
            return redirect('dashboard:settings')
        else:
            messages.error(request, _('Please correct the errors below.'))
    else:
        form = UserSettingsForm(instance=request.user)

    context = {
        'form': form,
    }
    return render(request, 'dashboard/settings.html', context)


@login_required
def analytics_page(request):
    """
    Analytics dashboard page.

    Displays charts and metrics using Chart.js with data from the analytics service.
    """
    # Get date range from query params (default 30 days)
    days = request.GET.get('days', '30')
    try:
        days = int(days)
    except ValueError:
        days = 30

    # Cap at reasonable limits
    days = max(1, min(days, 365))

    date_range = DateRange.last_n_days(days)
    service = AnalyticsService(request.user, date_range)

    # Get all analytics data
    overview = service.get_overview_stats()
    message_trend = service.get_message_volume_trend()
    conversation_trend = service.get_conversation_trend()
    response_time_trend = service.get_response_time_trend()
    platform_breakdown = service.get_platform_breakdown()
    response_types = service.get_response_type_distribution()
    status_distribution = service.get_conversation_status_distribution()
    ai_confidence = service.get_ai_confidence_distribution()
    top_replies = service.get_top_predefined_replies()
    busiest_hours = service.get_busiest_hours()
    usage = service.get_usage_stats()
    knowledge_base = service.get_knowledge_base_stats()

    context = {
        'days': days,
        'overview': overview,
        'usage': usage,
        'knowledge_base': knowledge_base,
        'top_replies': top_replies,
        # JSON data for charts
        'message_trend_json': json.dumps(message_trend),
        'conversation_trend_json': json.dumps(conversation_trend),
        'response_time_trend_json': json.dumps(response_time_trend),
        'platform_breakdown_json': json.dumps(platform_breakdown),
        'response_types_json': json.dumps(response_types),
        'status_distribution_json': json.dumps(status_distribution),
        'ai_confidence_json': json.dumps(ai_confidence),
        'busiest_hours_json': json.dumps(busiest_hours),
    }

    return render(request, 'dashboard/analytics.html', context)
