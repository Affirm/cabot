from django.db import models
from cabot.metricsapp.models import MetricsSourceBase


class GrafanaInstance(models.Model):
    class Meta:
        app_label = 'grafanaapp'

    name = models.CharField(
        unique=True,
        max_length=30,
        help_text='Unique name for Grafana site.'
    )
    url = models.CharField(
        max_length=100,
        help_text='Url of Grafana site.'
    )
    api_token = models.CharField(
        max_length=100,
        help_text='Grafana API token for authentication (http://docs.grafana.org/http_api/auth/).'
    )
    sources = models.ManyToManyField(
        MetricsSourceBase,
        through='GrafanaDataSource',
        help_text='Metrics sources used by this Grafana site.'
    )

    def __unicode__(self):
        return self.name


class GrafanaDataSource(models.Model):
    """Intermediate model with names for each data source used by a Grafana instance"""
    class Meta:
        app_label = 'grafanaapp'

    grafana_source_name = models.CharField(
        max_length=30,
        help_text='Name for a data source in grafana (e.g.metrics-prod-live")'
    )
    grafana_instance = models.ForeignKey(GrafanaInstance)
    metrics_source_base = models.ForeignKey(MetricsSourceBase)
