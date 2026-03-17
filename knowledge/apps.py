from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    name = 'knowledge'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # Import signals to register them
        import knowledge.signals  # noqa
