from django.contrib.auth.models import User
from django.test import TestCase
from mock import patch
import os
import yaml
from cabot.cabotapp.models import Service
from cabot.metricsapp.models import MetricsStatusCheckBase, MetricsSourceBase
from cabot.metricsapp import defs


def get_content(filename):
    path = os.path.join(os.path.dirname(__file__), 'fixtures/%s' % filename)
    with open(path) as f:
        return f.read()


def mock_get_series(*args):
    return yaml.load(get_content('metrics_series.yaml'))


def get_series_error(*args):
    return yaml.load(get_content('metrics_error.yaml'))


def mock_get_empty_series(*args):
    return {'error': False, 'raw': 'rawstuff', 'data': []}


def mock_time():
    return 1387817760.0


class TestMetricsBase(TestCase):
    """Test cases for _run() in MetricsStatusCheckBase"""
    def setUp(self):
        self.user = User.objects.create_user('user')
        self.source = MetricsSourceBase.objects.create(name='source')
        self.metrics_check = MetricsStatusCheckBase(
            name='test',
            created_by=self.user,
            source=self.source,
            check_type='<=',
            warning_value=9.0,
        )

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_failure(self):
        result, tags = self.metrics_check._run()
        self.assertEqual(result.check, self.metrics_check)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'WARNING prod.good.data: 9.2 not <= 9.0')
        self.assertEqual(tags, ['warning:prod.good.data'])

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_success(self):
        self.metrics_check.warning_value = 10.0
        result, tags = self.metrics_check._run()
        self.assertEqual(result.check, self.metrics_check)
        self.assertTrue(result.succeeded)
        self.assertIsNone(result.error)
        self.assertEqual(tags, [])

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_lte(self):
        # maximum value in the series
        self.metrics_check.warning_value = 9.66092
        self.metrics_check.save()
        result, tags = self.metrics_check._run()
        self.assertTrue(result.succeeded)

        self.metrics_check.warning_value = 9.66091
        self.metrics_check.save()
        result, tags = self.metrics_check._run()
        self.assertFalse(result.succeeded)

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_lt(self):
        self.metrics_check.check_type = '<'
        # maximum value in the series
        self.metrics_check.warning_value = 9.66092
        self.metrics_check.save()
        result, tags = self.metrics_check._run()
        self.assertFalse(result.succeeded)

        self.metrics_check.warning_value = 9.660921
        self.metrics_check.save()
        result, tags = self.metrics_check._run()
        self.assertTrue(result.succeeded)

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_gte(self):
        self.metrics_check.check_type = '>='
        # minimum value in the series
        self.metrics_check.warning_value = 1.16092
        self.metrics_check.save()
        result, tags = self.metrics_check._run()
        self.assertTrue(result.succeeded)

        self.metrics_check.warning_value = 1.16093
        self.metrics_check.save()
        result, tags = self.metrics_check._run()
        self.assertFalse(result.succeeded)

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_gt(self):
        self.metrics_check.check_type = '>'
        # minimum value in the series
        self.metrics_check.warning_value = 1.16092
        self.metrics_check.save()
        result, tags = self.metrics_check._run()
        self.assertFalse(result.succeeded)

        self.metrics_check.warning_value = 1.160915
        self.metrics_check.save()
        result, tags = self.metrics_check._run()
        self.assertTrue(result.succeeded)

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    def test_no_datapoints(self):
        """
        Run check at the current time (all the points are outdated). Should succeed
        """
        result, tags = self.metrics_check._run()
        self.assertEqual(result.check, self.metrics_check)
        self.assertTrue(result.succeeded)
        self.assertIsNone(result.error)

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', get_series_error)
    def test_error(self):
        result, tags = self.metrics_check._run()
        self.assertEqual(result.check, self.metrics_check)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, 'Error fetching metric from source: None')
        self.assertEqual(tags, ['fetch_error'])

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    def test_raw_data(self):
        result, tags = self.metrics_check._run()
        series = mock_get_series()
        threshold = {'series': 'alert.warning_threshold', 'datapoints': [[1387817760, 9.0], [1387818600, 9.0]]}
        series['data'].append(threshold)
        self.assertEqual(eval(result.raw_data), series['data'])


class TestMultipleThresholds(TestCase):
    """Test cases relating to multiple alert thresholds"""
    def setUp(self):
        self.user = User.objects.create_user('user')
        self.source = MetricsSourceBase.objects.create(name='source')
        self.metrics_check = MetricsStatusCheckBase(
            name='multi',
            created_by=self.user,
            source=self.source,
            check_type='<=',
            warning_value=9.0,
            high_alert_value=11.0,
            high_alert_importance=Service.CRITICAL_STATUS
        )

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_warning(self):
        """Test cases with both high alert and warning values"""
        result, tags = self.metrics_check._run()
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'WARNING prod.good.data: 9.2 not <= 9.0')
        self.assertEqual(self.metrics_check.importance, Service.WARNING_STATUS)
        self.assertEqual(tags, ['warning:prod.good.data'])

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_critical(self):
        self.metrics_check.high_alert_value = 9.5
        result, tags = self.metrics_check._run()
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'CRITICAL prod.good.data: 9.7 not <= 9.5')
        self.assertEqual(self.metrics_check.importance, Service.CRITICAL_STATUS)
        self.assertEqual(tags, ['critical:prod.good.data', 'warning:prod.good.data'])

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_error(self):
        self.metrics_check.high_alert_value = 9.5
        self.metrics_check.high_alert_importance = Service.ERROR_STATUS
        result, tags = self.metrics_check._run()
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'ERROR prod.good.data: 9.7 not <= 9.5')
        self.assertEqual(self.metrics_check.importance, Service.ERROR_STATUS)
        self.assertEqual(tags, ['error:prod.good.data', 'warning:prod.good.data'])

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_success(self):
        self.metrics_check.warning_value = 10.0
        result, tags = self.metrics_check._run()
        self.assertTrue(result.succeeded)
        self.assertIsNone(result.error)
        self.assertEqual(tags, [])

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_multiple_thresholds(self):
        result, tags = self.metrics_check._run()
        series = mock_get_series()

        warning_threshold = {'series': 'alert.warning_threshold',
                             'datapoints': [[1387817760, 9.0], [1387818600, 9.0]]}
        series['data'].append(warning_threshold)
        critical_threshold = {'series': 'alert.high_alert_threshold',
                              'datapoints': [[1387817760, 11.0], [1387818600, 11.0]]}
        series['data'].append(critical_threshold)
        self.assertEqual(eval(result.raw_data), series['data'])

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_warning_only(self):
        """Check only has a warning value"""
        self.metrics_check.high_alert_value = None
        result, tags = self.metrics_check._run()
        self.assertEqual(result.check, self.metrics_check)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'WARNING prod.good.data: 9.2 not <= 9.0')
        self.assertEqual(self.metrics_check.importance, Service.WARNING_STATUS)
        self.assertEqual(tags, ['warning:prod.good.data'])

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_high_alert_only(self):
        """Check only has a high alert value"""
        self.metrics_check.warning_value = None
        self.metrics_check.high_alert_value = 9.0
        result, tags = self.metrics_check._run()
        self.assertEqual(result.check, self.metrics_check)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'CRITICAL prod.good.data: 9.2 not <= 9.0')
        self.assertEqual(self.metrics_check.importance, Service.CRITICAL_STATUS)
        self.assertEqual(tags, ['critical:prod.good.data'])

        # It should also work for warnings
        self.metrics_check.warning_value = 9.0
        self.metrics_check.high_alert_value = 10.0
        result, tags = self.metrics_check._run()
        self.assertEqual(result.check, self.metrics_check)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'WARNING prod.good.data: 9.2 not <= 9.0')
        self.assertEqual(self.metrics_check.importance, Service.WARNING_STATUS)
        self.assertEqual(tags, ['warning:prod.good.data'])

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_consecutive_failures(self):
        """
        Check that if the series contains enough consecutive failed points, a
        high alert is raised.
        """
        self.metrics_check.consecutive_failures = 2

        # Verify that it works for high alerts (error, critical)
        self.metrics_check.warning_value = 8.0
        self.metrics_check.high_alert_value = 9.0
        result, tags = self.metrics_check._run()
        self.assertEqual(result.check, self.metrics_check)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'CRITICAL prod.good.data: 2 consecutive points not <= 9.0')
        self.assertEqual(self.metrics_check.importance, Service.CRITICAL_STATUS)
        self.assertEqual(tags, ['critical:prod.good.data', 'warning:prod.good.data', 'warning:stage.cool.data'])

        # It should also work for warnings
        self.metrics_check.warning_value = 9.0
        self.metrics_check.high_alert_value = 10.0
        result, tags = self.metrics_check._run()
        self.assertEqual(result.check, self.metrics_check)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'WARNING prod.good.data: 2 consecutive points not <= 9.0')
        self.assertEqual(self.metrics_check.importance, Service.WARNING_STATUS)
        self.assertEqual(tags, ['warning:prod.good.data'])

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_not_enough_consecutive_failures(self):
        """
        Check that if the series contains failed points, but not enough are
        consecutive, that a high alert is NOT raised.
        """
        self.metrics_check.consecutive_failures = 3

        # Not enough points above the high-alert threshold, so we should get a warning
        self.metrics_check.warning_value = 8.0
        self.metrics_check.high_alert_value = 9.0
        result, tags = self.metrics_check._run()
        self.assertEqual(result.check, self.metrics_check)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'WARNING prod.good.data: 3 consecutive points not <= 8.0')
        self.assertEqual(self.metrics_check.importance, Service.WARNING_STATUS)
        self.assertEqual(tags, ['warning:prod.good.data', 'warning:stage.cool.data'])

        # Not enough points above the warning threshold, so we shouldn't get an alert
        self.metrics_check.warning_value = 9.0
        self.metrics_check.high_alert_value = 10.0
        result, tags = self.metrics_check._run()
        self.assertTrue(result.succeeded)
        self.assertIsNone(result.error)
        self.assertEqual(tags, [])

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase.get_series', mock_get_series)
    @patch('time.time', mock_time)
    def test_thresholds_dont_cause_alerts(self):
        """
        Check that threshold data isn't treated as metrics data and thus causes
        an alert.
        """

        # The danger is that _get_raw_data_with_thresholds() in cabot/metricsapp/api/base.py
        # will modify the series data while we are still examining that data for
        # alerts, and the threshold points themselves are found to be in violation.
        # Note, our check-type cannot use equality, so we'll use less-than here.
        self.metrics_check.check_type = '<'

        # Our code should find
        self.metrics_check.warning_value = 9.0
        self.metrics_check.high_alert_value = 10.0
        self.metrics_check.consecutive_failures = 2
        result, tags = self.metrics_check._run()
        self.assertFalse(result.succeeded)
        # If this fails, we might see:
        # "CRITICAL alert.high_alert_threshold: 2 consecutive points not < 10.0"
        self.assertEqual(result.error, u'WARNING prod.good.data: 2 consecutive points not < 9.0')
        self.assertEqual(tags, ['warning:prod.good.data'])


class TestEmptySeries(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('user')
        self.source = MetricsSourceBase.objects.create(name='source')
        self.check = MetricsStatusCheckBase(
            name='test',
            created_by=self.user,
            source=self.source,
            check_type='>',
            warning_value=10,
            high_alert_value=5,
            high_alert_importance=Service.CRITICAL_STATUS,
        )

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase._get_parsed_data', mock_get_empty_series)
    @patch('time.time', mock_time)
    def test_fill_single_zero_by_default(self):
        # _get_parsed_data() does not get filled. We expect an empty array.
        self.assertEqual(self.check._get_parsed_data()['data'], [])
        # get_series() is filled
        expected = [{'datapoints': [[mock_time(), 0.0]], 'series': 'no_data_fill_0'}]
        self.assertEqual(self.check.get_series()['data'], expected)
        # The test should fail
        result = self.check._run()
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'CRITICAL no_data_fill_0: 0.0 not > 5.0')
        self.assertEqual(self.check.importance, Service.CRITICAL_STATUS)

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase._get_parsed_data', mock_get_empty_series)
    @patch('time.time', mock_time)
    def test_immediate_success(self):
        self.check.on_empty_series = defs.ON_EMPTY_SERIES_PASS
        # Points should not be filled in
        self.assertEqual(self.check.get_series()['data'], [])
        # The test should succeed
        result = self.check._run()
        self.assertTrue(result.succeeded)
        self.assertEqual(result.error, u'SUCCESS: no data')

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase._get_parsed_data', mock_get_empty_series)
    @patch('time.time', mock_time)
    def test_immediate_warning(self):
        self.check.on_empty_series = defs.ON_EMPTY_SERIES_WARN
        # Points should not be filled in
        self.assertEqual(self.check.get_series()['data'], [])
        # The test should warn
        result = self.check._run()
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'WARNING: no data')
        self.assertEqual(self.check.importance, Service.WARNING_STATUS)

    @patch('cabot.metricsapp.models.MetricsStatusCheckBase._get_parsed_data', mock_get_empty_series)
    @patch('time.time', mock_time)
    def test_immediate_failure(self):
        self.check.on_empty_series = defs.ON_EMPTY_SERIES_FAIL
        # Points should not be filled in
        self.assertEqual(self.check.get_series()['data'], [])
        # The test should fail and respect the high_alert_importance (ERROR here)
        self.check.high_alert_importance = Service.ERROR_STATUS
        result = self.check._run()
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'ERROR: no data')
        self.assertEqual(self.check.importance, Service.ERROR_STATUS)
        # This time it should fail with CRITICAL
        self.check.high_alert_importance = Service.CRITICAL_STATUS
        result = self.check._run()
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, u'CRITICAL: no data')
        self.assertEqual(self.check.importance, Service.CRITICAL_STATUS)
