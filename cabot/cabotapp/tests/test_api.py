import threading

from django.test import Client
from rest_framework import status, HTTP_HEADER_ENCODING
from rest_framework.reverse import reverse as api_reverse
import base64
import json
from datetime import datetime, timedelta
from mock import patch

from rest_framework.test import APITransactionTestCase

from cabot.cabotapp.models import (
    ActivityCounter,
    StatusCheck,
    JenkinsStatusCheck,
    Service,
    clone_model,
    HttpStatusCheck)
from .utils import LocalTestCase


# from https://www.caktusgroup.com/blog/2009/05/26/testing-django-views-for-concurrency-issues/
def run_concurrently(times):
    """
    Add this decorator to small pieces of code that you want to test
    concurrently to make sure they don't raise exceptions when run at the
    same time.  E.g., some Django views that do a SELECT and then a subsequent
    INSERT might fail when the INSERT assumes that the data has not changed
    since the SELECT.
    """
    def test_concurrently_decorator(test_func):
        def wrapper(*args, **kwargs):
            exceptions = []

            def call_test_func():
                try:
                    test_func(*args, **kwargs)
                except Exception, e:
                    exceptions.append(e)
                    raise

            threads = []
            for i in range(times):
                threads.append(threading.Thread(target=call_test_func))
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            if exceptions:
                raise Exception('test_concurrently intercepted %s exceptions: %s' % (len(exceptions), exceptions))
        return wrapper
    return test_concurrently_decorator


class TestAPI(LocalTestCase):
    def setUp(self):
        super(TestAPI, self).setUp()

        self.basic_auth = 'Basic {}'.format(
            base64.b64encode(
                '{}:{}'.format(self.username, self.password).encode(HTTP_HEADER_ENCODING)
            ).decode(HTTP_HEADER_ENCODING)
        )

        self.start_data = {
            'service': [
                {
                    'name': u'Service',
                    'users_to_notify': [],
                    'alerts_enabled': True,
                    'status_checks': [10101, 10102, 10103],
                    'alerts': [],
                    'hackpad_id': None,
                    'id': 2194,
                    'url': u''
                },
            ],
            'statuscheck': [
                {
                    'name': u'Jenkins Check',
                    'active': True,
                    'importance': u'ERROR',
                    'frequency': 5,
                    'retries': 0,
                    'id': 10101
                },
                {
                    'name': u'Http Check',
                    'active': True,
                    'importance': u'CRITICAL',
                    'frequency': 5,
                    'retries': 0,
                    'id': 10102
                },
                {
                    'name': u'TCP Check',
                    'active': True,
                    'importance': u'ERROR',
                    'frequency': 5,
                    'retries': 0,
                    'id': 10103
                },
                {
                    'name': u'Jenkins Check 2',
                    'active': True,
                    'importance': u'ERROR',
                    'frequency': 5,
                    'retries': 0,
                    'id': 10104
                },
            ],
            'jenkinsstatuscheck': [
                {
                    'name': u'Jenkins Check',
                    'active': True,
                    'importance': u'ERROR',
                    'frequency': 5,
                    'retries': 0,
                    'max_queued_build_time': 10,
                    'max_build_failures': 5,
                    'id': 10101
                },
                {
                    'name': u'Jenkins Check 2',
                    'active': True,
                    'importance': u'ERROR',
                    'frequency': 5,
                    'retries': 0,
                    'max_queued_build_time': 10,
                    'max_build_failures': 0,
                    'id': 10104
                },
            ],
            'httpstatuscheck': [
                {
                    'name': u'Http Check',
                    'active': True,
                    'importance': u'CRITICAL',
                    'frequency': 5,
                    'retries': 0,
                    'endpoint': u'http://arachnys.com',
                    'username': None,
                    'password': None,
                    'text_match': None,
                    'status_code': u'200',
                    'timeout': 10,
                    'verify_ssl_certificate': True,
                    'id': 10102
                },
            ],
            'tcpstatuscheck': [
                {
                    'name': u'TCP Check',
                    'active': True,
                    'importance': u'ERROR',
                    'frequency': 5,
                    'retries': 0,
                    'address': 'github.com',
                    'port': 80,
                    'timeout': 6,
                    'id': 10103
                },
            ],
        }
        self.post_data = {
            'service': [
                {
                    'name': u'posted service',
                    'users_to_notify': [],
                    'alerts_enabled': True,
                    'status_checks': [],
                    'alerts': [],
                    'hackpad_id': None,
                    'id': 2194,
                    'url': u'',
                },
            ],
            'jenkinsstatuscheck': [
                {
                    'name': u'posted jenkins check',
                    'active': True,
                    'importance': u'CRITICAL',
                    'frequency': 5,
                    'retries': 0,
                    'max_queued_build_time': 37,
                    'max_build_failures': 5,
                    'id': 10101
                },
            ],
            'httpstatuscheck': [
                {
                    'name': u'posted http check',
                    'active': True,
                    'importance': u'ERROR',
                    'frequency': 5,
                    'retries': 0,
                    'endpoint': u'http://arachnys.com/post_tests',
                    'username': None,
                    'password': None,
                    'text_match': u'text',
                    'status_code': u'201',
                    'timeout': 30,
                    'verify_ssl_certificate': True,
                    'id': 10102
                },
            ],
            'tcpstatuscheck': [
                {
                    'name': u'posted tcp check',
                    'active': True,
                    'importance': u'ERROR',
                    'frequency': 5,
                    'retries': 0,
                    'address': 'github.com',
                    'port': 80,
                    'timeout': 6,
                    'id': 10103
                },
            ],
        }

    def test_auth_failure(self):
        response = self.client.get(api_reverse('statuscheck-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def normalize_dict(self, operand):
        for key, val in operand.items():
            if isinstance(val, list):
                operand[key] = sorted(val)
        return operand

    def test_gets(self):
        for model, items in self.start_data.items():
            response = self.client.get(api_reverse('{}-list'.format(model)),
                                       format='json', HTTP_AUTHORIZATION=self.basic_auth)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), len(items))
            for response_item, item in zip(response.data, items):
                self.assertEqual(self.normalize_dict(response_item), item)
            for item in items:
                response = self.client.get(api_reverse('{}-detail'.format(model), args=[item['id']]),
                                           format='json', HTTP_AUTHORIZATION=self.basic_auth)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(self.normalize_dict(response.data), item)

    def test_posts(self):
        for model, items in self.post_data.items():
            for item in items:
                # hackpad_id and other null text fields omitted on create
                # for now due to rest_framework bug:
                # https://github.com/tomchristie/django-rest-framework/issues/1879
                # Update: This has been fixed in master:
                # https://github.com/tomchristie/django-rest-framework/pull/1834
                for field in ('hackpad_id', 'username', 'password'):
                    if field in item:
                        del item[field]
                create_response = self.client.post(api_reverse('{}-list'.format(model)),
                                                   format='json', data=item, HTTP_AUTHORIZATION=self.basic_auth)
                self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
                self.assertTrue('id' in create_response.data)
                item['id'] = create_response.data['id']
                for field in ('hackpad_id', 'username', 'password'):  # See comment above
                    if field in create_response.data:
                        item[field] = None
                self.assertEqual(self.normalize_dict(create_response.data), item)
                get_response = self.client.get(api_reverse('{}-detail'.format(model), args=[item['id']]),
                                               format='json', HTTP_AUTHORIZATION=self.basic_auth)
                self.assertEqual(self.normalize_dict(get_response.data), item)


class TestAPIFiltering(LocalTestCase):
    def setUp(self):
        super(TestAPIFiltering, self).setUp()

        self.expected_filter_result = JenkinsStatusCheck.objects.create(
            name='Filter test 1',
            retries=True,
            importance=Service.CRITICAL_STATUS,
        )
        JenkinsStatusCheck.objects.create(
            name='Filter test 2',
            retries=True,
            importance=Service.WARNING_STATUS,
        )
        JenkinsStatusCheck.objects.create(
            name='Filter test 3',
            retries=False,
            importance=Service.CRITICAL_STATUS,
        )

        self.expected_sort_names = [u'Filter test 1', u'Filter test 2', u'Filter test 3', u'Jenkins Check',
                                    u'Jenkins Check 2']

        self.basic_auth = 'Basic {}'.format(
            base64.b64encode(
                '{}:{}'.format(self.username, self.password)
                       .encode(HTTP_HEADER_ENCODING)
            ).decode(HTTP_HEADER_ENCODING)
        )

    def test_query(self):
        response = self.client.get(
            '{}?retries=1&importance=CRITICAL'.format(
                api_reverse('jenkinsstatuscheck-list')
            ),
            format='json',
            HTTP_AUTHORIZATION=self.basic_auth
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['id'],
            self.expected_filter_result.id
        )

    def test_positive_sort(self):
        response = self.client.get(
            '{}?ordering=name'.format(
                api_reverse('jenkinsstatuscheck-list')
            ),
            format='json',
            HTTP_AUTHORIZATION=self.basic_auth
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item['name'] for item in response.data],
            self.expected_sort_names
        )

    def test_negative_sort(self):
        response = self.client.get(
            '{}?ordering=-name'.format(
                api_reverse('jenkinsstatuscheck-list')
            ),
            format='json',
            HTTP_AUTHORIZATION=self.basic_auth
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item['name'] for item in response.data],
            self.expected_sort_names[::-1]
        )


class TestActivityCounterAPI(APITransactionTestCase):
    LAST_ENABLED_TIME = datetime(2018, 8, 15, 1, 1, 1)
    LAST_DISABLED_TIME = datetime(2018, 8, 15, 2, 2, 2)

    def setUp(self):
        self.http_check = HttpStatusCheck.objects.create(
            id=10102,
            name='Http Check',
            frequency=5,
        )
        super(TestActivityCounterAPI, self).setUp()

    def _set_activity_counter(self, enabled, count):
        '''Utility function to set the activity counter for the http check'''
        self.http_check.use_activity_counter = enabled
        self.http_check.save()
        ActivityCounter.objects.create(
            status_check=self.http_check,
            count=count,
            last_enabled=(None if count == 0 else self.LAST_ENABLED_TIME),
            last_disabled=None,
        )

    def _get_activity_counter(self):
        'Return the activity counter for the http check. Will look it up in the DB.'
        return ActivityCounter.objects.get(status_check=self.http_check,)

    def test_counter_get(self):
        self._set_activity_counter(True, 0)
        url = '/api/status-checks/activity-counter?'
        expected_body = {
            'check.id': 10102,
            'check.name': 'Http Check',
            'check.run_delay': 0,
            'counter.count': 0,
            'counter.enabled': True,
            'counter.last_enabled': '',
            'counter.last_disabled': '',
        }
        # Get by id
        response = self.client.get(url + 'id=10102')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.content), expected_body)
        # Get by name
        response = self.client.get(url + 'name=Http Check')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.content), expected_body)

    def test_counter_get_error_on_duplicate_names(self):
        self._set_activity_counter(True, 1)
        # If two checks have the same name, check that we error out.
        # This should not be an issue once we enforce uniqueness on the name.
        clone_model(self.http_check)
        self.assertEqual(len(StatusCheck.objects.filter(name='Http Check')), 2)
        url = '/api/status-checks/activity-counter?name=Http Check'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @patch('cabot.cabotapp.models.timezone.now')
    def test_counter_incr(self, mock_now):
        mock_now.return_value = self.LAST_ENABLED_TIME
        self._set_activity_counter(True, 0)
        url = '/api/status-checks/activity-counter?id=10102'
        expected_body = {
            'check.id': 10102,
            'check.name': 'Http Check',
            'check.run_delay': 0,
            'counter.count': 0,
            'counter.enabled': True,
            'counter.last_enabled': '',
            'counter.last_disabled': '',
        }
        # Counter starts at zero
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.content), expected_body)
        # Increment counter to one
        expected_body['counter.count'] = 1
        expected_body['counter.last_enabled'] = '2018-08-15 01:01:01'
        expected_body['detail'] = 'counter incremented to 1'
        response = self.client.get(url + '&action=incr')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.content), expected_body)
        self.assertEqual(StatusCheck.objects.filter(id=10102)[0].activity_counter.count, 1)

    @patch('cabot.cabotapp.models.timezone.now')
    def test_counter_decr(self, mock_now):
        mock_now.return_value = self.LAST_DISABLED_TIME
        self._set_activity_counter(True, 2)
        url = '/api/status-checks/activity-counter?id=10102&action=decr'
        expected_body = {
            'check.id': 10102,
            'check.name': 'Http Check',
            'check.run_delay': 0,
            'counter.count': 1,
            'counter.enabled': True,
            'counter.last_enabled': '2018-08-15 01:01:01',
            'counter.last_disabled': '',
            'detail': 'counter decremented to 1',
        }
        # Decrement counter from two to one
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.content), expected_body)
        self.assertEqual(StatusCheck.objects.filter(id=10102)[0].activity_counter.count, 1)
        # Decrement counter from two to zero
        expected_body['counter.count'] = 0
        expected_body['counter.last_disabled'] = '2018-08-15 02:02:02'
        expected_body['detail'] = 'counter decremented to 0'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.content), expected_body)
        self.assertEqual(StatusCheck.objects.filter(id=10102)[0].activity_counter.count, 0)
        # Decrementing when counter is zero has no effect
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.content), expected_body)

    @patch('cabot.cabotapp.models.timezone.now')
    def test_counter_reset(self, mock_now):
        mock_now.return_value = self.LAST_DISABLED_TIME
        self._set_activity_counter(True, 11)
        url = '/api/status-checks/activity-counter?id=10102&action=reset'
        expected_body = {
            'check.id': 10102,
            'check.name': 'Http Check',
            'check.run_delay': 0,
            'counter.count': 0,
            'counter.enabled': True,
            'counter.last_enabled': '2018-08-15 01:01:01',
            'counter.last_disabled': '2018-08-15 02:02:02',
            'detail': 'counter reset to 0',
        }
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.content), expected_body)
        self.assertEqual(StatusCheck.objects.filter(id=10102)[0].activity_counter.count, 0)

    def test_check_should_run_when_activity_counter_disabled(self):
        self._set_activity_counter(False, 0)
        self.assertTrue(self.http_check.should_run())

    def test_check_should_run_when_activity_counter_positive(self):
        self._set_activity_counter(True, 1)
        self.assertTrue(self.http_check.should_run())

    def test_check_should_not_run_when_activity_counter_zero(self):
        self._set_activity_counter(True, 0)
        self.assertFalse(self.http_check.should_run())

    def test_check_should_not_run_when_activity_counter_missing(self):
        # Set use_activity_counter=True, but do NOT create the actual activity
        # counter DB entry. This used to cause a run_all_checks() to throw a
        # DoesNotExist exception.
        self.http_check.use_activity_counter = True
        self.http_check.save()
        self.assertFalse(self.http_check.should_run())

    def test_check_should_not_run_when_activity_counter_is_default(self):
        # Specifically, the check should not run when last_enabled is None and count is 0
        self._set_activity_counter(True, 0)
        counter = self._get_activity_counter()
        self.assertTrue(self.http_check.use_activity_counter)
        self.assertEqual(counter.count, 0)
        self.assertIsNone(counter.last_enabled)
        self.assertFalse(self.http_check.should_run())

    def test_existing_check_should_run_if_counter_is_positive(self):
        # By 'existing' I mean that the counter value is > 0, but the last_enabled
        # and last_disabled fields are not (yet) set. In this case the check should
        # still run.
        self.http_check.use_activity_counter = True
        self.http_check.save()
        counter = ActivityCounter.objects.create(status_check=self.http_check, count=4)
        self.assertIsNone(counter.last_enabled)
        self.assertIsNone(counter.last_disabled)
        self.assertTrue(self.http_check.should_run())

    def test_check_should_run_should_set_last_enabled_if_null(self):
        # This tests the behavior of should_run(), and under what circumstances
        # it should set the last_enabled field.
        #
        # NB: we use self._get_activity_counter() instead of just saving the counter
        # as a local variable, because we want to test the latest values in the DB.

        # Create the activity_counter
        self._set_activity_counter(True, 0)

        # Make sure last_enabled is None
        self.assertTrue(self.http_check.use_activity_counter)
        self.assertIsNone(self._get_activity_counter().last_enabled)

        # Even though use_activity_counter is True, should_run() will not set last_enabled
        # because the count is 0 and last_enabled is None (a special case).
        self.assertFalse(self.http_check.should_run())
        self.assertIsNone(self._get_activity_counter().last_enabled)

        # Once count is positive and we need last_enabled, it'll be set
        counter = self._get_activity_counter()
        counter.count = 4
        counter.save()
        self.assertTrue(self.http_check.should_run())
        self.assertIsNotNone(self._get_activity_counter().last_enabled)

    @patch('cabot.cabotapp.models.timezone.now')
    def test_check_should_run_with_delay(self, mock_now):
        # Use the following times:
        #
        # - last_enabled  = T+0
        # - last_disabled = T+60
        # - run_delay     = 30 mins
        #
        # The check should thus run between T+30 and T+90
        self._set_activity_counter(True, 1)
        self.http_check.run_delay = 30
        self.http_check.save()
        counter = self._get_activity_counter()

        # Assume it is 15 mins after check was enabled. Check should not run right now.
        mock_now.return_value = counter.last_enabled + timedelta(minutes=15)
        self.assertFalse(self.http_check.should_run())

        # Check should run if now >= run_delay (30 minutes)
        mock_now.return_value = counter.last_enabled + timedelta(minutes=30)
        self.assertTrue(self.http_check.should_run())

        # Now assume the check ran recently. It shouldn't run again until the frequency is up.
        self.http_check.last_run = counter.last_enabled + timedelta(minutes=31)
        self.http_check.save()

        mock_now.return_value = counter.last_enabled + timedelta(minutes=32)
        self.assertFalse(self.http_check.should_run())

        mock_now.return_value = counter.last_enabled + timedelta(minutes=37)
        self.assertTrue(self.http_check.should_run())

        # Finally, reset the counter and set the last_disabled time to last_enabled + 60.
        # The check should not run if after the disabled time (last_enabled + 90).
        mock_now.return_value = counter.last_enabled + timedelta(minutes=60)
        counter.reset_and_save()

        # - Though the counter is 0, the current time is still less than last_disabled + run_delay,
        #   so the check should still run.
        mock_now.return_value = counter.last_enabled + timedelta(minutes=89)
        self.assertTrue(self.http_check.should_run())

        # - The current time is past last_disabled + run_delay, so the check should not run.
        mock_now.return_value = counter.last_enabled + timedelta(minutes=91)
        self.assertFalse(self.http_check.should_run())

    def test_counter_incr_concurrent(self):
        self._set_activity_counter(True, 0)
        url = '/api/status-checks/activity-counter?id=10102&action=incr'

        @run_concurrently(20)
        def do_requests():
            c = Client()
            c.get(url)

            # manually close DB connection, otherwise it stays open and tests can't terminate cleanly
            from django.db import connection
            connection.close()
        do_requests()

        counter = ActivityCounter.objects.get(status_check=10102)
        self.assertEqual(counter.count, 20)
