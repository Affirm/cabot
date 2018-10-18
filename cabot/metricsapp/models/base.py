from django.core.urlresolvers import reverse
from django.db import models
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

    source = models.ForeignKey('MetricsSourceBase')
    check_type = models.CharField(
        choices=CHECK_TYPES,
        max_length=30
    )
    warning_value = models.FloatField(
        null=True,
        blank=True,
        help_text='If this expression evaluates to False, the check will fail with a warning. Checks may have '
                  'both warning and high alert values, or only one.'
    )
    high_alert_importance = models.CharField(
        max_length=30,
        choices=IMPORTANCES,
        default=Service.ERROR_STATUS,
        help_text='Severity level for a high alert failure. Critical alerts are for things you want to wake you '
                  'up, and errors are for things you can fix the next morning.'
    )
    high_alert_value = models.FloatField(
        null=True,
        blank=True,
        help_text='If this expression evaluates to False, the check will fail with an error or critical level alert.'
    )
    time_range = models.IntegerField(
        default=defs.METRIC_STATUS_TIME_RANGE_DEFAULT,
        help_text='Time range in minutes the check gathers data for.',
    )
    grafana_panel = models.ForeignKey(
        'GrafanaPanel',
        null=True
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
    empty_series_handler = models.CharField(
        choices=defs.EMPTY_SERIES_HANDLERS,
        default='fill_one',
        max_length=16,
        help_text='How to handle an empty metrics series. Options are: succeed immediately, fail immediately, fill '
                  'a single data point, fill all data points. Fill options use the \'empty_series_fill_value\' below.'
    )
    empty_series_fill_value = models.FloatField(
        default=0.0,
        null=True,
        blank=True,
        help_text='Value used to fill in an empty series.'
    )

    def _run(self):
        """Run a status check"""
        return run_metrics_check(self)

    def get_series(self):
        """
        Implemented by subclasses.
        Parse raw data from a data source into the format
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
        :param check: the status check
        :return the parsed data
        """
        parsed_data = self._get_parsed_data()
        self._fill_empty_series(parsed_data)
        return parsed_data

    def _get_data_point_frequency(self):
        '''
        Get the frequency of data points in the series
        :return: Frequency in seconds, or None
        '''
        raise NotImplementedError('Subclasses must implement')

    def _get_parsed_data(self):
        '''
        To be implemented by subclasses. Should parse raw data from the data source and
        return it in the format mentioned in `get_series()`.
        '''
        raise NotImplementedError('MetricsStatusCheckBase has no data source.')

    def _fill_empty_series(self, parsed_data):
        '''
        Given a dict of parsed data, if the data series is empty and we are configured to
        fill in a value, do so.
        '''
        # If there's no data, and the empty_series_handler is configured to fill, do so
        if parsed_data['data'] == []:
            if self.empty_series_handler == defs.EMPTY_SERIES_FILL_ONE:
                datapoints = [[int(time.time()), self.empty_series_fill_value]]
                parsed_data['data'].append(dict(series='no_data_fill_one', datapoints=datapoints))
            elif self.empty_series_handler == defs.EMPTY_SERIES_FILL_ALL:
                datapoints = self._get_filled_points()
                parsed_data['data'].append(dict(series='no_data_fill_all', datapoints=datapoints))

    def _get_filled_points(self):
        '''
        Compute and return the list of all points to be filled in when a data series is empty.
        Assumes the empty_series_method is FILL_ALL and empty_series_fill_value is populated.
        :return: List of data points.
        '''
        # All times in seconds
        freq = self._get_data_point_frequency()
        if freq is None or freq <= 0:
            raise ValueError('Expected positive frequency, got {}'.format(str(freq)))
        total_time = self.time_range * 60
        now = int(time.time())
        last_time = now - (now % freq)
        curr_time = last_time
        points = []
        # Fill points until we have filled the entire time range
        while last_time - curr_time <= total_time:
            points.append([curr_time, self.empty_series_fill_value])
            curr_time -= freq
        return points

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

    def duplicate(self, inst_set=(), serv_set=()):
        new_check = self
        new_check.pk = None
        new_check.id = None
        new_check.statuscheck_ptr_id = None
        new_check.metricsstatuscheckbase_ptr_id = None
        new_check.name = 'Copy of {}'.format(self.name)
        new_check.last_run = None
        new_check.save()
        for linked in list(inst_set) + list(serv_set):
            linked.status_checks.add(new_check)
        return new_check.pk
