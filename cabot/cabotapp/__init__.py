from django.apps import AppConfig
from django.db.models.signals import post_migrate

default_app_config = 'cabot.cabotapp.CabotConfig'


def post_migrate_callback(**kwargs):
    from cabot.cabotapp.alert import update_alert_plugins
    update_alert_plugins()


class CabotConfig(AppConfig):
    name = 'cabot.cabotapp'

    def ready(self):
        import cabot.cabotapp.signals  # noqa
        post_migrate.connect(post_migrate_callback)
