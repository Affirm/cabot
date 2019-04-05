# -*- coding: utf-8 -*-

from datetime import timedelta, datetime
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from cabot.cabotapp import tasks
from mock import patch, call
from cabot.cabotapp.models import HttpStatusCheck, Service, clone_model, ActivityCounter
from cabot.cabotapp.tasks import update_service, update_all_services
from .utils import (
    LocalTestCase,
    fake_jenkins_success,
    fake_jenkins_response,
    jenkins_blocked_response,
    fake_http_200_response,
    fake_http_404_response,
    fake_tcp_success,
    fake_tcp_failure,
    throws_timeout,
)


class TestCheckRun(LocalTestCase):

    def test_calculate_service_status(self):
        self.assertEqual(self.jenkins_check.calculated_status,
                         Service.CALCULATED_PASSING_STATUS)
        self.assertEqual(self.http_check.calculated_status,
                         Service.CALCULATED_PASSING_STATUS)
        self.assertEqual(self.tcp_check.calculated_status,
                         Service.CALCULATED_PASSING_STATUS)
        self.service.update_status()
        self.assertEqual(self.service.overall_status, Service.PASSING_STATUS)

        # Now two most recent are failing
        self.most_recent_result.succeeded = False
        self.most_recent_result.save()
        self.http_check.last_run = timezone.now()
        self.http_check.save()
        self.assertEqual(self.http_check.calculated_status,
                         Service.CALCULATED_FAILING_STATUS)
        self.service.update_status()
        self.assertEqual(self.service.overall_status, Service.CRITICAL_STATUS)

        # Will fail even if second one is working
        self.older_result.succeeded = True
        self.older_result.save()
        self.http_check.save()
        self.assertEqual(self.http_check.calculated_status,
                         Service.CALCULATED_FAILING_STATUS)
        self.service.update_status()
        self.assertEqual(self.service.overall_status, Service.CRITICAL_STATUS)

        # Changing the number of retries will change it up
        self.http_check.retries = 1
        self.http_check.save()
        self.assertEqual(self.http_check.calculated_status,
                         Service.CALCULATED_PASSING_STATUS)
        self.service.update_status()
        self.assertEqual(self.service.overall_status, Service.PASSING_STATUS)

    @patch('cabot.cabotapp.jenkins.requests.get', fake_jenkins_success)
    def test_jenkins_success(self):
        checkresults = self.jenkins_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 0)
        self.jenkins_check.run()
        checkresults = self.jenkins_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 1)
        self.assertTrue(self.jenkins_check.last_result().succeeded)
        self.assertFalse(self.jenkins_check.last_result().tags.exists())

    @patch('cabot.cabotapp.jenkins.requests.get', fake_jenkins_response)
    def test_jenkins_run(self):
        checkresults = self.jenkins_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 0)
        self.jenkins_check.run()
        checkresults = self.jenkins_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 1)
        self.assertFalse(self.jenkins_check.last_result().succeeded)
        self.assertEqual(list(self.jenkins_check.last_result().tags.values_list('value', flat=True)), ['bad_response'])

    @patch('cabot.cabotapp.jenkins.requests.get', fake_jenkins_success)
    def test_jenkins_consecutive_failures(self):
        checkresults = self.jenkins_check2.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 0)
        self.jenkins_check2.run()
        checkresults = self.jenkins_check2.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 1)
        self.assertFalse(self.jenkins_check2.last_result().succeeded)
        self.assertEqual(list(self.jenkins_check2.last_result().tags.values_list('value', flat=True)),
                         ['max_consecutive_failures_exceeded'])

    @patch('cabot.cabotapp.jenkins.requests.get', jenkins_blocked_response)
    def test_jenkins_blocked_build(self):
        checkresults = self.jenkins_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 0)
        self.jenkins_check.run()
        checkresults = self.jenkins_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 1)
        self.assertFalse(self.jenkins_check.last_result().succeeded)
        self.assertEqual(list(self.jenkins_check.last_result().tags.values_list('value', flat=True)),
                         ['max_queued_build_time_exceeded'])

    @patch('cabot.cabotapp.models.requests.get', throws_timeout)
    def test_timeout_handling_in_jenkins(self):
        checkresults = self.jenkins_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 0)
        self.jenkins_check.run()
        checkresults = self.jenkins_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 1)
        self.assertFalse(self.jenkins_check.last_result().succeeded)
        self.assertIn(u'Error fetching from Jenkins - something bad happened',
                      self.jenkins_check.last_result().error)
        self.assertEqual(list(self.jenkins_check.last_result().tags.values_list('value', flat=True)),
                         ['bad_response'])

    @patch('cabot.cabotapp.models.requests.request', fake_http_200_response)
    def test_http_run(self):
        checkresults = self.http_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 2)
        self.http_check.run()
        checkresults = self.http_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 3)
        self.assertTrue(self.http_check.last_result().succeeded)
        self.assertEqual(self.http_check.calculated_status,
                         Service.CALCULATED_PASSING_STATUS)
        self.http_check.text_match = u'blah blah'
        self.http_check.save()
        self.http_check.run()
        self.assertFalse(self.http_check.last_result().succeeded)
        self.assertEqual(self.http_check.calculated_status,
                         Service.CALCULATED_FAILING_STATUS)
        self.assertEqual(list(self.http_check.last_result().tags.values_list('value', flat=True)),
                         ['text_match_failed'])

        # Unicode
        self.http_check.text_match = u'This is not in the http response!!'
        self.http_check.save()
        self.http_check.run()
        self.assertFalse(self.http_check.last_result().succeeded)
        self.assertEqual(self.http_check.calculated_status,
                         Service.CALCULATED_FAILING_STATUS)
        self.assertEqual(list(self.http_check.last_result().tags.values_list('value', flat=True)),
                         ['text_match_failed'])

    @patch('cabot.cabotapp.models.requests.request', throws_timeout)
    def test_timeout_handling_in_http(self):
        checkresults = self.http_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 2)
        self.http_check.run()
        checkresults = self.http_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 3)
        self.assertFalse(self.http_check.last_result().succeeded)
        self.assertIn(u'Request error occurred: something bad happened',
                      self.http_check.last_result().error)
        self.assertEqual(list(self.http_check.last_result().tags.values_list('value', flat=True)),
                         ['RequestException'])

    @patch('cabot.cabotapp.models.requests.request', fake_http_404_response)
    def test_http_run_bad_resp(self):
        checkresults = self.http_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 2)
        self.http_check.run()
        checkresults = self.http_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 3)
        self.assertFalse(self.http_check.last_result().succeeded)
        self.assertEqual(self.http_check.calculated_status,
                         Service.CALCULATED_FAILING_STATUS)
        self.assertEqual(list(self.http_check.last_result().tags.values_list('value', flat=True)),
                         ['status:404'])

    @patch('cabot.cabotapp.models.socket.create_connection', fake_tcp_success)
    def test_tcp_success(self):
        checkresults = self.tcp_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 0)
        self.tcp_check.run()
        checkresults = self.tcp_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 1)
        self.assertTrue(self.tcp_check.last_result().succeeded)
        self.assertEqual(list(self.tcp_check.last_result().tags.values_list('value', flat=True)), [])

    @patch('cabot.cabotapp.models.socket.create_connection', fake_tcp_failure)
    def test_tcp_failure(self):
        checkresults = self.tcp_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 0)
        self.tcp_check.run()
        checkresults = self.tcp_check.statuscheckresult_set.all()
        self.assertEqual(len(checkresults), 1)
        self.assertFalse(self.tcp_check.last_result().succeeded)
        self.assertFalse(self.tcp_check.last_result().error, 'timed out')
        self.assertEqual(list(self.tcp_check.last_result().tags.values_list('value', flat=True)), ['ETIMEDOUT'])

    def test_update_service(self):
        service_id = self.service.id
        self.assertEqual(self.jenkins_check.calculated_status,
                         Service.CALCULATED_PASSING_STATUS)
        self.assertEqual(self.http_check.calculated_status,
                         Service.CALCULATED_PASSING_STATUS)
        self.assertEqual(self.tcp_check.calculated_status,
                         Service.CALCULATED_PASSING_STATUS)
        update_service.apply((service_id,)).get()
        self.assertEqual(Service.objects.get(id=service_id).overall_status, Service.PASSING_STATUS)

        # Now two most recent are failing
        self.most_recent_result.succeeded = False
        self.most_recent_result.save()
        self.http_check.last_run = timezone.now()
        self.http_check.save()
        self.assertEqual(self.http_check.calculated_status,
                         Service.CALCULATED_FAILING_STATUS)
        update_service.apply((service_id,)).get()
        self.assertEqual(Service.objects.get(id=service_id).overall_status, Service.CRITICAL_STATUS)

    def test_update_all_services(self):
        service_id = self.service.id
        self.assertEqual(self.jenkins_check.calculated_status,
                         Service.CALCULATED_PASSING_STATUS)
        self.assertEqual(self.http_check.calculated_status,
                         Service.CALCULATED_PASSING_STATUS)
        self.assertEqual(self.tcp_check.calculated_status,
                         Service.CALCULATED_PASSING_STATUS)
        update_all_services.apply().get()
        self.assertEqual(Service.objects.get(id=service_id).overall_status, Service.PASSING_STATUS)

        # Now two most recent are failing
        self.most_recent_result.succeeded = False
        self.most_recent_result.save()
        self.http_check.last_run = timezone.now()
        self.http_check.save()
        self.assertEqual(self.http_check.calculated_status,
                         Service.CALCULATED_FAILING_STATUS)
        update_all_services.apply().get()
        self.assertEqual(Service.objects.get(id=service_id).overall_status, Service.CRITICAL_STATUS)


class TestStatusCheck(LocalTestCase):

    def test_duplicate_statuscheck(self):
        """
        Test that duplicating a statuscheck works and creates a check
        with the name we expect.
        """
        http_checks = HttpStatusCheck.objects.filter(polymorphic_ctype__model='httpstatuscheck')
        self.assertEqual(len(http_checks), 1)

        self.http_check.duplicate()

        http_checks = HttpStatusCheck.objects.filter(polymorphic_ctype__model='httpstatuscheck')
        self.assertEqual(len(http_checks), 2)

        new = http_checks.filter(name__icontains='Copy of')[0]
        old = http_checks.exclude(name__icontains='Copy of')[0]

        # New check should be the same as the old check except for the name
        self.assertEqual(new.name, 'Copy of {}'.format(old.name))
        self.assertEqual(new.endpoint, old.endpoint)
        self.assertEqual(new.status_code, old.status_code)

    @patch('cabot.cabotapp.tasks.run_status_check')
    def test_run_all(self, mock_run_status_check):
        tasks.run_all_checks()
        mock_run_status_check.assert_has_calls([
            call.apply_async((10102,), queue='normal_checks'),
            call.apply_async((10101,), queue='normal_checks'),
            call.apply_async((10104,), queue='normal_checks'),
            call.apply_async((10103,), queue='normal_checks'),
        ])

    def test_check_should_run_if_never_run_before(self):
        self.assertEqual(self.http_check.last_run, None)
        self.assertTrue(self.http_check.should_run())

    def test_check_should_run_based_on_frequency(self):
        freq_mins = 5

        # The check should run if not run within the frequency
        self.http_check.frequency = freq_mins
        self.http_check.last_run = timezone.now() - timedelta(minutes=freq_mins+1)
        self.http_check.save()
        self.assertTrue(self.http_check.should_run())

        # The check should NOT run if run within the frequency
        self.http_check.last_run = timezone.now() - timedelta(minutes=freq_mins-1)
        self.http_check.save()
        self.assertFalse(self.http_check.should_run())

    def test_clean_validates_unique_name(self):
        self.http_check.use_activity_counter = True
        self.http_check.save()

        # Duplicate the check
        clone_model(self.http_check)
        models = HttpStatusCheck.objects.filter(name=self.http_check.name)
        self.assertEqual(len(models), 2)
        check_1, check_2 = models

        # If both have their activity counters enabled, then clean() should raise
        self.assertTrue(check_1.use_activity_counter)
        self.assertTrue(check_2.use_activity_counter)
        with self.assertRaises(ValidationError):
            check_1.clean()

        # If one does not use activity counters, clean() should not raise
        check_2.use_activity_counter = False
        check_2.save()
        check_1.clean()


class TestActivityCounter(TestCase):

    def setUp(self):
        self.counter = ActivityCounter()

    def test_activity_counter_defaults(self):
        self.assertEqual(self.counter.count, 0)
        self.assertIsNone(self.counter.last_enabled)
        self.assertIsNone(self.counter.last_disabled)

    @patch('cabot.cabotapp.models.ActivityCounter.save')
    @patch('cabot.cabotapp.models.timezone.now')
    def test_activity_counter_increment_and_save(self, mock_now, mock_save):
        now1 = datetime(2018, 12, 10, 1, 1, 1)
        now2 = datetime(2018, 12, 10, 2, 2, 2)

        # First increment sets last_enabled
        mock_now.return_value = now1
        self.counter.increment_and_save()
        self.assertEqual(self.counter.count, 1)
        self.assertEqual(self.counter.last_enabled, now1)
        self.assertIsNone(self.counter.last_disabled)
        self.assertEqual(mock_save.call_count, 1)

        # Second call increments counter, last_enabled stays the same
        mock_now.return_value = now2
        self.counter.increment_and_save()
        self.assertEqual(self.counter.count, 2)
        self.assertEqual(self.counter.last_enabled, now1)
        self.assertEqual(mock_save.call_count, 2)

    @patch('cabot.cabotapp.models.ActivityCounter.save')
    @patch('cabot.cabotapp.models.timezone.now')
    def test_activity_counter_decrement_and_save(self, mock_now, mock_save):
        now = datetime(2018, 12, 10, 1, 1, 1)
        mock_now.return_value = now

        # At counter of 0, nothing happens
        self.counter.decrement_and_save()
        self.assertEqual(self.counter.count, 0)
        self.assertIsNone(self.counter.last_enabled)
        self.assertIsNone(self.counter.last_disabled)
        self.assertEqual(mock_now.call_count, 0)
        self.assertEqual(mock_save.call_count, 0)

        # At count of 1, decrement and set last_disabled
        self.counter.count = 1
        self.counter.decrement_and_save()
        self.assertEqual(self.counter.count, 0)
        self.assertIsNone(self.counter.last_enabled)
        self.assertEqual(self.counter.last_disabled, now)
        self.assertEqual(mock_now.call_count, 1)
        self.assertEqual(mock_save.call_count, 1)

    @patch('cabot.cabotapp.models.ActivityCounter.save')
    @patch('cabot.cabotapp.models.timezone.now')
    def test_activity_counter_reset_and_save(self, mock_now, mock_save):
        now = datetime(2018, 12, 10, 1, 1, 1)
        mock_now.return_value = now

        # At counter of 0, nothing happens
        self.counter.reset_and_save()
        self.assertEqual(self.counter.count, 0)
        self.assertIsNone(self.counter.last_enabled)
        self.assertIsNone(self.counter.last_disabled)
        self.assertEqual(mock_now.call_count, 0)
        self.assertEqual(mock_save.call_count, 0)

        # At positive count, update counter and last_disabled
        self.counter.count = 42
        self.counter.reset_and_save()
        self.assertEqual(self.counter.count, 0)
        self.assertIsNone(self.counter.last_enabled)
        self.assertEqual(self.counter.last_disabled, now)
        self.assertEqual(mock_now.call_count, 1)
        self.assertEqual(mock_save.call_count, 1)
