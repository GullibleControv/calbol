"""
Analytics Service for CalBol.
Provides aggregated metrics for the analytics dashboard.
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q


class DateRange:
    """Helper for creating date range tuples."""

    def __init__(self, start, end):
        self.start = start
        self.end = end

    def __iter__(self):
        return iter((self.start, self.end))

    @classmethod
    def last_n_days(cls, days: int) -> 'DateRange':
        end = timezone.now()
        start = end - timedelta(days=days)
        return cls(start, end)


class AnalyticsService:
    """Compute analytics metrics for a user within a date range."""

    def __init__(self, user, date_range: DateRange):
        self.user = user
        self.start = date_range.start
        self.end = date_range.end

    def _messages(self):
        from conversations.models import Message
        return Message.objects.filter(
            conversation__user=self.user,
            created_at__range=(self.start, self.end)
        )

    def _conversations(self):
        from conversations.models import Conversation
        return Conversation.objects.filter(
            user=self.user,
            created_at__range=(self.start, self.end)
        )

    def get_overview_stats(self) -> dict:
        msgs = self._messages()
        total = msgs.count()
        ai_count = msgs.filter(response_type='ai').count()
        predefined_count = msgs.filter(response_type='predefined').count()
        manual_count = msgs.filter(response_type='manual').count()
        avg_confidence = msgs.filter(response_type='ai').aggregate(
            avg=Avg('ai_confidence')
        )['avg'] or 0

        return {
            'total_messages': total,
            'ai_responses': ai_count,
            'predefined_responses': predefined_count,
            'manual_responses': manual_count,
            'avg_confidence': round(float(avg_confidence), 2),
            'automation_rate': round((ai_count + predefined_count) / total * 100, 1) if total else 0,
        }

    def get_message_volume_trend(self) -> list:
        """Daily message counts for the period."""
        from conversations.models import Message
        from django.db.models.functions import TruncDate

        rows = (
            Message.objects
            .filter(conversation__user=self.user, created_at__range=(self.start, self.end))
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        return [{'date': str(r['date']), 'count': r['count']} for r in rows]

    def get_conversation_trend(self) -> list:
        """Daily new conversation counts."""
        from conversations.models import Conversation
        from django.db.models.functions import TruncDate

        rows = (
            Conversation.objects
            .filter(user=self.user, created_at__range=(self.start, self.end))
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        return [{'date': str(r['date']), 'count': r['count']} for r in rows]

    def get_response_time_trend(self) -> list:
        """Average response processing time per day (ms)."""
        from conversations.models import Message
        from django.db.models.functions import TruncDate

        rows = (
            Message.objects
            .filter(
                conversation__user=self.user,
                created_at__range=(self.start, self.end),
                direction='outbound',
                processing_time_ms__isnull=False
            )
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(avg_ms=Avg('processing_time_ms'))
            .order_by('date')
        )
        return [{'date': str(r['date']), 'avg_ms': round(r['avg_ms'] or 0)} for r in rows]

    def get_platform_breakdown(self) -> list:
        """Message counts per platform type."""
        from conversations.models import Message

        rows = (
            Message.objects
            .filter(conversation__user=self.user, created_at__range=(self.start, self.end))
            .values('conversation__platform__platform_type')
            .annotate(count=Count('id'))
        )
        return [
            {'platform': r['conversation__platform__platform_type'] or 'unknown', 'count': r['count']}
            for r in rows
        ]

    def get_response_type_distribution(self) -> list:
        """Count by response type (ai, predefined, manual, fallback)."""
        rows = (
            self._messages()
            .filter(direction='outbound')
            .values('response_type')
            .annotate(count=Count('id'))
        )
        return [{'type': r['response_type'] or 'unknown', 'count': r['count']} for r in rows]

    def get_conversation_status_distribution(self) -> list:
        """Count of conversations by status."""
        from conversations.models import Conversation

        rows = (
            Conversation.objects
            .filter(user=self.user)
            .values('status')
            .annotate(count=Count('id'))
        )
        return [{'status': r['status'], 'count': r['count']} for r in rows]

    def get_ai_confidence_distribution(self) -> list:
        """Bucket AI confidence scores into bands."""
        from conversations.models import Message

        msgs = Message.objects.filter(
            conversation__user=self.user,
            response_type='ai',
            ai_confidence__isnull=False,
            created_at__range=(self.start, self.end)
        )
        bands = {'0-40%': 0, '40-60%': 0, '60-80%': 0, '80-100%': 0}
        for m in msgs.values_list('ai_confidence', flat=True):
            if m < 0.4:
                bands['0-40%'] += 1
            elif m < 0.6:
                bands['40-60%'] += 1
            elif m < 0.8:
                bands['60-80%'] += 1
            else:
                bands['80-100%'] += 1
        return [{'band': k, 'count': v} for k, v in bands.items()]

    def get_top_predefined_replies(self) -> list:
        """Top 10 predefined replies by use count."""
        from replies.models import PredefinedReply

        return list(
            PredefinedReply.objects
            .filter(user=self.user, is_active=True)
            .order_by('-use_count')[:10]
            .values('name', 'use_count')
        )

    def get_busiest_hours(self) -> list:
        """Message count grouped by hour of day."""
        from conversations.models import Message
        from django.db.models.functions import ExtractHour

        rows = (
            Message.objects
            .filter(conversation__user=self.user, created_at__range=(self.start, self.end))
            .annotate(hour=ExtractHour('created_at'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )
        return [{'hour': r['hour'], 'count': r['count']} for r in rows]

    def get_usage_stats(self) -> dict:
        limit = self.user.get_plan_limit()
        return {
            'monthly_replies': self.user.monthly_replies,
            'monthly_ai_replies': self.user.monthly_ai_replies,
            'monthly_limit': limit if limit != float('inf') else None,
            'plan': self.user.plan,
        }

    def get_knowledge_base_stats(self) -> dict:
        from knowledge.models import Document, DocumentChunk

        doc_count = Document.objects.filter(user=self.user).count()
        processed = Document.objects.filter(user=self.user, processed=True).count()
        chunk_count = DocumentChunk.objects.filter(document__user=self.user).count()
        return {
            'total_documents': doc_count,
            'processed_documents': processed,
            'total_chunks': chunk_count,
        }
