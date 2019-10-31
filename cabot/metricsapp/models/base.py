from django.urls import reverse
from django.db import models, transaction
from django.core.validators import MinValueValidator
from cabot.cabotapp.models import Service, StatusCheck
from cabot.cabotapp.utils import build_absolute_url
from cabot.metricsapp.api import run_metrics_check
from cabot.cabotapp.defs import CHECK_TYPES
from cabot.metricsapp import defs
import time


class MetricsSourceBase(models.Model):
    class Meta:
        app_label = 'metricsapp'

    name = models.CharField(
        unique=True,
        max_length=30,
        help_text='Unique name for the data source',
    )

    def __unicode__(self):
        return self.name


class MetricsStatusCheckBase(StatusCheck):
    class Meta:
        app_label = 'metricsapp'

    @property
    def update_url(self):
        if self.grafana_panel is not None:
            return 'grafana-edit'
        # Panels not from Grafana can only be edited by admins
        return 'check'

    IMPORTANCES = (
        (Service.ERROR_STATUS, 'Error'),
        (Service.CRITICAL_STATUS, 'Critical'),
    )

    source = models.ForeignKey('MetricsSourceBase', on_delete=models.CASCADE)
    check_type = models.CharField(
        choices=CHECK_TYPES,
        max_length=30,
        verbose_name='Comparison operator',
        help_text='Comparison operator to use when comparing data point values against a threshold. The check will '
                  'succeed if the expression "value operator threshold" (e.g. 10 >= 4) is true.'
    )
    warning_value = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Warning threshold',
        help_text='Threshold to use for warnings. A check may have a warning threshold, failure threshold, or both.'
    )
    high_alert_importance = models.CharField(
        max_length=30,
        choices=IMPORTANCES,
        default=Service.ERROR_STATUS,
        verbose_name='Failure severity',
        help_text='Severity level for a failure. Choose "critical" if the alert needs immediate attention, '
                  'and "error" if you can fix it tomorrow morning.'
    )
    high_alert_value = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Failure threshold',
        help_text='Threshold to use for failures (error or critical). A check may have a warning threshold, '
                  'failure threshold, or both.'
    )
    time_range = models.IntegerField(
        default=defs.METRIC_STATUS_TIME_RANGE_DEFAULT,
        help_text='Time range in minutes the check gathers data for.',
    )
    grafana_panel = models.ForeignKey(
        'GrafanaPanel',
        null=True,
        on_delete=models.CASCADE,
    )
    auto_sync = models.NullBooleanField(
        default=True,
        null=True,
        help_text='For Grafana status checks--should Cabot poll Grafana for dashboard updates and automatically '
                  'update the check?'
    )
    consecutive_failures = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Number of consecutive data points that must exceed the alert '
                  'threshold before an alert is triggered. Applies to both warning '
                  'and high-alert thresholds.',
    )
    on_empty_series = models.CharField(
        choices=defs.ON_EMPTY_SERIES_OPTIONS,
        default=defs.ON_EMPTY_SERIES_FILL_ZERO,
        max_length=16,
        help_text='Action to take if the series is empty. Options are: pass, warn, or fail immediately, '
                  'or insert a single data point with value zero.'
    )

    tag_fetch_error = "fetch_error"
    tag_no_data = "no_data"

    @staticmethod
    def tag_failing(importance, series_name):
        # type: (str, str) -> str
        return "{}:{}".format(importance.lower(), series_name)

    def _run(self):
        """Run a status check"""
        return run_metrics_check(self)

    def get_series(self):
        """
        Fetches time series data, optionally fills it (if configured to do so via the on_empty_series field),
        and returns the series.
        :param check: the status check
        :return the time series data
        """
        series = self._get_parsed_data()
        self._fill_parsed_data(series)
        return series

    def _get_parsed_data(self):
        '''
        To be implemented by subclasses. Parse the raw data from a data source into the format:

            status:
            error_message:
            error_code:
            raw:
            # Parsed data
            data:
              - series: a.b.c.d
                datapoints:
                  - [timestamp, value]
                  - [timestamp, value]
              - series: a.b.c.p.q
                datapoints:
                  - [timestamp, value]

        :return: the parsed data
        '''
        raise NotImplementedError('MetricsStatusCheckBase has no data source.')

    def _fill_parsed_data(self, series):
        '''Given the parsed series data, if it is empty and should be filled, fill it.'''
        if series['data'] == []:
            if self.on_empty_series == defs.ON_EMPTY_SERIES_FILL_ZERO:
                series['data'].append(dict(series='no_data_fill_0', datapoints=[[int(time.time()), 0]]))

    def get_url_for_check(self):
        """Get the url for viewing this check"""
        return build_absolute_url(reverse('check', kwargs={'pk': self.pk}))

    def get_status_image(self):
        """Return a Grafana png image for the check if it exists"""
        if self.grafana_panel is not None:
            return self.grafana_panel.get_rendered_image()
        return None

    def get_status_link(self):
        """Return a link from Grafana with more information about the check."""
        if self.grafana_panel is not None:
            return self.grafana_panel.modifiable_url
        return None

    @transaction.atomic
    def duplicate(self, inst_set=(), serv_set=()):
        new_check = self
        new_check.pk = None
        new_check.id = None
        new_check.statuscheck_ptr_id = None
        new_check.metricsstatuscheckbase_ptr_id = None
        new_check.name = 'Copy of {}'.format(self.name)
        new_check.last_run = None
        if self.grafana_panel:
            new_panel = self.grafana_panel
            new_panel.pk = None
            new_panel.id = None
            new_panel.save()
            new_check.grafana_panel = new_panel
        new_check.save()
        for linked in list(inst_set) + list(serv_set):
            linked.status_checks.add(new_check)
        return new_check.pk
