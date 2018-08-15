from urlparse import urlparse

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase

from cabot.cabotapp.models import Service
from cabot.metricsapp.models import MetricsSourceBase, ElasticsearchStatusCheck


class TestMetricsReviewChanges(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('user', email='user@example.com', password='password')
        self.source = MetricsSourceBase.objects.create(name='source')
        self.metrics_check = ElasticsearchStatusCheck.objects.create(
            name='test',
            created_by=self.user,
            source=self.source,
            check_type='<=',
            warning_value=9.0,
            high_alert_value=15.0,
            retries=0,
            time_range=30,
            frequency=5,
            queries='{}',
        )

        self.base_check_data = {
            'name': 'test',
            'queries': '{}',
            'active': True,
            'auto_sync': True,
            'check_type': '<=',
            'warning_value': 9.0,

            'high_alert_importance': Service.ERROR_STATUS,
            'high_alert_value': 15.0,
            'consecutive_failures': 1,
            'time_range': 30,
            'retries': 0,
            'frequency': 5,
            'ignore_final_data_point': True,
            'use_activity_counter': False,
            'runbook': '',
            'skip_review': False,
        }

        logged_in = self.client.login(username='user', password='password')
        self.assertTrue(logged_in)

    def test_review_changes(self):
        data = self.base_check_data.copy()
        data['name'] = 'ultra cool test'
        data['skip_review'] = False

        response = self.client.post(reverse('grafana-es-update', kwargs={'pk': self.metrics_check.pk}), data=data)
        self.assertNotContains(response, "errorlist", status_code=200, msg_prefix=str(response))

        # DB should NOT be updated yet
        self.metrics_check = ElasticsearchStatusCheck.objects.get(pk=self.metrics_check.pk)
        self.assertEqual(self.metrics_check.name, 'test')

        # now accept the changes by manually setting skip_review to True (which should be done in the response)
        # (would ideally do this by using a browser's normal submit routine on the response,
        # but I don't think we can do that with just django's standard testing functions)
        data['skip_review'] = True
        response = self.client.post(reverse('grafana-es-update', kwargs={'pk': self.metrics_check.pk}), data=data)

        # verify that we ended up at the success url (/check/<pk>)
        self.assertEqual(urlparse(response.url).path, reverse('check', kwargs={'pk': self.metrics_check.pk}))

        # DB should be updated, verify the name changed
        self.metrics_check = ElasticsearchStatusCheck.objects.get(pk=self.metrics_check.pk)
        self.assertEqual(self.metrics_check.name, 'ultra cool test')

    def test_review_changes_no_changes(self):
        # no changes to the check
        data = self.base_check_data.copy()
        data['skip_review'] = False

        response = self.client.post(reverse('grafana-es-update', kwargs={'pk': self.metrics_check.pk}), data=data)
        # if this starts returning 200, there's a form error
        self.assertNotContains(response, "errorlist", status_code=302, msg_prefix=str(response))

        # verify that we ended up at the success url (/check/<pk>)
        self.assertEqual(urlparse(response.url).path, reverse('check', kwargs={'pk': self.metrics_check.pk}))

        new_metrics_check = ElasticsearchStatusCheck.objects.get(pk=self.metrics_check.pk)
        self.assertEqual(self.metrics_check, new_metrics_check)