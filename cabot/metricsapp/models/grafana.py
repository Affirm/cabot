import requests
import urlparse
from django.core.exceptions import ValidationError
from django.db import models
from cabot.metricsapp.api import get_grafana_auth_headers
from .base import MetricsSourceBase


class GrafanaInstance(models.Model):
    class Meta:
        app_label = 'metricsapp'

    name = models.CharField(
        unique=True,
        max_length=30,
        help_text='Unique name for Grafana site.'
    )
    url = models.CharField(
        max_length=100,
        help_text='Url of Grafana site.'
    )
    api_key = models.CharField(
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

    def clean(self, *args, **kwargs):
        """Make sure the input url/api key work"""
        response = requests.get(urlparse.urljoin(self.url, 'api/search'),
                                headers=get_grafana_auth_headers(self.api_key))

        if response.status_code != 200:
            raise ValidationError('Request to Grafana API failed.')


class GrafanaDataSource(models.Model):
    """
    Intermediate model to match the name of a data source in a Grafana instance
    with the corresponding MetricsDataSource
    """
    class Meta:
        app_label = 'metricsapp'

    grafana_source_name = models.CharField(
        max_length=30,
        help_text='The name for a data source in grafana (e.g. metrics-stage")'
    )
    grafana_instance = models.ForeignKey(GrafanaInstance)
    metrics_source_base = models.ForeignKey(MetricsSourceBase)

    def __unicode__(self):
        return '{} ({}, {})'.format(self.grafana_source_name, self.metrics_source_base.name,
                                    self.grafana_instance.name)
