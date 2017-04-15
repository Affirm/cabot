from django.contrib.auth.models import User
from django.test import TestCase
from elasticsearch_dsl import Search
from elasticsearch_dsl.response import Response
from mock import patch
import json
from cabot.cabotapp.models import Service
from cabot.metricsapp.api import validate_query
from cabot.metricsapp.models import ElasticsearchSource, ElasticsearchStatusCheck
from cabot.metricsapp.tests.test_metrics_base import get_content


class TestElasticsearchSource(TestCase):
    def setUp(self):
        self.es_source = ElasticsearchSource.objects.create(
            name='elastigirl',
            urls='localhost'
        )

    def test_client(self):
        client = self.es_source.client
        self.assertIn('localhost', repr(client))

    def test_multiple_clients(self):
        self.es_source.urls = 'localhost,127.0.0.1'
        self.es_source.save()
        client = self.es_source.client
        self.assertIn('localhost', repr(client))
        self.assertIn('127.0.0.1', repr(client))

    def test_client_whitespace(self):
        """Whitespace should be stripped from the urls"""
        self.es_source.urls = '\nlocalhost,       globalhost'
        self.es_source.save()
        client = self.es_source.client
        self.assertIn('localhost', repr(client))
        self.assertIn('globalhost', repr(client))
        self.assertNotIn('\nlocalhost', repr(client))
        self.assertNotIn(' globalhost', repr(client))


def empty_es_response(*args):
    return Response(Search(), [])


def get_es(file):
    return json.loads(get_content(file))


def fake_es_response(*args):
    return Response(Search(), get_es('es_response.json'))


def fake_es_multiple_metrics_terms(*args):
    return Response(Search(), get_es('es_multiple_metrics_terms.json'))


def fake_es_percentile(*args):
    return Response(Search(), get_es('es_percentile.json'))


def fake_es_multiple_terms(*args):
    return Response(Search(), get_es('es_multiple_terms.json'))


class TestElasticsearchStatusCheck(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('user')
        self.es_source = ElasticsearchSource.objects.create(
            name='es',
            urls='localhost'
        )
        self.es_check = ElasticsearchStatusCheck.objects.create(
            name='checkycheck',
            created_by=self.user,
            source=self.es_source,
            check_type='>=',
            warning_value=3.5,
            high_alert_importance='CRITICAL',
            high_alert_value=3.0,
            queries='[{"query": {"query_string": {"query": "name:affirm.i.love.metrics"}}, '
                    '"aggs": {"times": {"date_histogram": {"field": "@timestamp", "interval": "hour"}, '
                    '"aggs": {"avg_timing": {"avg": {"field": "timing"}}}}}}]'
        )

    @patch('cabot.metricsapp.models.elastic.Search.execute', fake_es_response)
    def test_query(self):
        # Test output series
        series = self.es_check.get_series()
        self.assertFalse(series['error'])
        self.assertEqual(series['raw'], get_es('es_response.json'))
        data = series['data']
        self.assertEqual(len(data), 1)

        data = data[0]
        # TODO: how to name series
        self.assertEqual(str(data['series']), 'avg')
        self.assertEqual(data['datapoints'], [[1491552000000, 4.9238095238095], [1491555600000, 4.7958115183246],
                                              [1491559200000, 3.53005464480873], [1491562800000, 4.04651162790697],
                                              [1491566400000, 4.8390501319261], [1491570000000, 4.51913477537437],
                                              [1491573600000, 4.4642857142857], [1491577200000, 4.81336405529953]])

        # Test check result
        result = self.es_check._run()
        self.assertTrue(result.succeeded)
        self.assertIsNone(result.error)

    def test_invalid_query(self):
        """Test that an invalid Elasticsearch query is returned as an error"""
        self.es_check.queries = 'definitely not elasticsearch at all'

        series = self.es_check.get_series()
        self.assertTrue(series['error'])
        self.assertEqual(series['error_code'], 'ValueError')

        result = self.es_check._run()
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, 'Error fetching metric from source')

    @patch('cabot.metricsapp.models.elastic.Search.execute', empty_es_response)
    def test_empty_response(self):
        """Test result when elasticsearch returns an empty response"""
        # TODO(elainearbaugh): a lot of validation
        series = self.es_check.get_series()
        self.assertTrue(series['error'])
        # TODO: which type of error should this be

        result = self.es_check._run()
        self.assertFalse(result.succeeded)
        self.assertEqual(result.error, 'Error fetching metric from source')

    @patch('cabot.metricsapp.models.elastic.Search.execute', fake_es_multiple_metrics_terms)
    def test_terms_aggregation(self):
        self.es_check.check_type = '<'
        self.es_check.warning_value = 15
        self.es_check.high_alert_value = 18
        series = self.es_check.get_series()
        self.assertFalse(series['error'])
        self.assertEqual(series['raw'], get_es('es_multiple_metrics_terms.json'))

        data = series['data']
        self.assertEqual(len(data), 4)

        self.assertEqual(str(data[0]['series']), 'maroon.max')
        self.assertEqual(data[0]['datapoints'], [[1491566400000, 17.602], [1491570000000, 15.953],
                                                 [1491573600000, 18.296], [1491577200000, 14.242]])
        self.assertEqual(str(data[1]['series']), 'maroon.min')
        self.assertEqual(data[1]['datapoints'], [[1491566400000, 17.603], [1491570000000, 15.954],
                                                 [1491573600000, 18.297], [1491577200000, 14.243]])
        self.assertEqual(str(data[2]['series']), 'gold.max')
        self.assertEqual(data[2]['datapoints'], [[1491566400000, 12.220], [1491570000000, 14.490],
                                                 [1491573600000, 14.400], [1491577200000, 17.460]])
        self.assertEqual(str(data[3]['series']), 'gold.min')
        self.assertEqual(data[3]['datapoints'], [[1491566400000, 12.221], [1491570000000, 14.491],
                                                 [1491573600000, 14.401], [1491577200000, 17.461]])

        # Test check result
        result = self.es_check._run()
        self.assertFalse(result.succeeded)
        self.assertEquals(result.error, 'maroon.max: 18.3 < 18.0')
        self.assertEqual(self.es_check.importance, Service.CRITICAL_STATUS)

    @patch('cabot.metricsapp.models.elastic.Search.execute', fake_es_percentile)
    def test_percentile(self):
        series = self.es_check.get_series()
        self.assertFalse(series['error'])
        self.assertEqual(series['raw'], get_es('es_percentile.json'))

        data = series['data']
        self.assertEqual(len(data), 3)

        self.assertEqual(str(data[0]['series']), '25.0')
        self.assertEqual(data[0]['datapoints'], [[1491566400000, 294.75], [1491570000000, 377.125],
                                                 [1491573600000, 403.0], [1491577200000, 703.6666666666666]])
        self.assertEqual(str(data[1]['series']), '50.0')
        self.assertEqual(data[1]['datapoints'], [[1491566400000, 1120.0], [1491570000000, 1124.0],
                                                 [1491573600000, 1138.3333333333333],
                                                 [1491577200000, 1114.3999999999999]])
        self.assertEqual(str(data[2]['series']), '75.0')
        self.assertEqual(data[2]['datapoints'], [[1491566400000, 1350.0], [1491570000000, 1299.0833333333333],
                                                 [1491573600000, 1321.875], [1491577200000, 1293.7333333333333]])

    @patch('cabot.metricsapp.models.elastic.Search.execute', fake_es_multiple_terms)
    def test_multiple_terms(self):
        series = self.es_check.get_series()
        self.assertFalse(series['error'])
        self.assertEqual(series['raw'], get_es('es_multiple_terms.json'))

        data = series['data']
        self.assertEqual(len(data), 3)

        self.assertEqual(str(data[0]['series']), 'north.west.min')
        self.assertEqual(data[0]['datapoints'], [[1491566400000, 15.0], [1491570000000, 15.0]])
        self.assertEqual(str(data[1]['series']), 'north.east.min')
        self.assertEqual(data[1]['datapoints'], [[1491566400000, 19.0], [1491570000000, 13.0]])
        self.assertEqual(str(data[2]['series']), 'south.west.min')
        self.assertEqual(data[2]['datapoints'], [[1491566400000, 16.0], [1491570000000, 15.0]])


class TestQueryValidation(TestCase):
    def test_valid_query(self):
        query = '{"aggs": {"agg": {"terms": {"field": "a1"},' \
                '"aggs": {"agg": {"terms": {"field": "b2"},' \
                '"aggs": {"agg": {"date_histogram": {"field": "@timestamp","interval": "hour"},' \
                '"aggs": {"max": {"max": {"field": "timing"}}}}}}}}}}'
        # Should not throw an exception
        validate_query(json.loads(query))

    def test_not_agg(self):
        """Aggregations must be named 'agg'"""
        query = '{"aggs": {"notagg": {"terms": {"field": "data"},' \
                '"aggs": {"agg": {"date_histogram": {"field": "@timestamp","interval": "hour"},' \
                '"aggs": {"max": {"max": {"field": "timing"}}}}}}}}}}'

        with self.assertRaises(ValueError) as e:
            validate_query(json.loads(query))
            self.assertEqual(e.exception, 'Elasticsearch query format error: aggregations should be named "agg"')

    def test_external_date_hist(self):
        """date_histogram must be the innermost aggregation"""
        query = '{"aggs": {"agg": {"date_histogram": {"field": "@timestamp","interval": "hour"},' \
                '"aggs": {"agg": {"terms": {"field": "data"},' \
                '"aggs": {"max": {"max": {"field": "timing"}}}}}}}}}}'

        with self.assertRaises(ValueError) as e:
            validate_query(json.loads(query))
            self.assertEqual(e.exception, 'Elasticsearch query format error: date_histogram must '
                                          'be the innermost aggregation (besides metrics)')

    def test_unsupported_metric(self):
        query = '{"aggs": {"agg": {"terms": {"field": "data"},' \
                '"aggs": {"agg": {"date_histogram": {"field": "@timestamp","interval": "hour"},' \
                '"aggs": {"raw_document": {"max": {"field": "timing"}}}}}}}}}}'

        with self.assertRaises(ValueError) as e:
            validate_query(json.loads(query))
            self.assertEqual(e.exception, 'Elasticsearch query format error: unsupported metric raw_document')

    def test_nonmatching_metric_name(self):
        query = '{"aggs": {"agg": {"terms": {"field": "data"},' \
                '"aggs": {"agg": {"date_histogram": {"field": "@timestamp","interval": "hour"},' \
                '"aggs": {"min": {"max": {"field": "timing"}}}}}}}}}}'

        with self.assertRaises(ValueError) as e:
            validate_query(json.loads(query))
            self.assertEqual(e.exception, 'Elasticsearch query format error: metric name must '
                                          'be the same as the metric type')
