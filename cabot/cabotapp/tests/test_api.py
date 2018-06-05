from rest_framework import status, HTTP_HEADER_ENCODING
from rest_framework.reverse import reverse as api_reverse
import base64
from cabot.cabotapp.models import JenkinsStatusCheck, Service
from .utils import LocalTestCase


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
            ],
            'jenkinsstatuscheck': [
                {
                    'name': u'Jenkins Check',
                    'active': True,
                    'importance': u'ERROR',
                    'frequency': 5,
                    'retries': 0,
                    'max_queued_build_time': 10,
                    'id': 10101
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

        self.expected_sort_names = [u'Filter test 1', u'Filter test 2', u'Filter test 3', u'Jenkins Check']

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