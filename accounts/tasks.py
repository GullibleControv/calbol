import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def reset_monthly_usage():
    """Reset monthly reply counters for all users on the 1st of each month."""
    from django.utils import timezone
    from .models import User

    now = timezone.now()
    if now.day != 1:
        return 'Skipped: not the 1st of the month'

    updated = User.objects.all().update(monthly_replies=0, monthly_ai_replies=0)
    logger.info(f"Monthly usage counters reset for {updated} users")
    return f'Reset {updated} users'
