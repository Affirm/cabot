from django.apps import AppConfig

default_app_config = 'cabot.metricsapp.CabotMetricsConfig'


class CabotMetricsConfig(AppConfig):
    name = 'cabot.metricsapp'

    def ready(self):
        import cabot.metricsapp.signals  # noqa
