from django.apps import AppConfig


class TechnomomConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'technomom'

    def ready(self):
        import technomom.signals  # noqa: F401
