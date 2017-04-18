import json
from django.core.exceptions import ValidationError
from django.test import TestCase
from cabot.metricsapp.api import build_query, template_response, validate_query
from .test_elasticsearch import get_json_file, get_content


class TestGrafanaQueryBuilder(TestCase):
    def test_grafana_query(self):
        series = get_json_file('grafana/query_builder/grafana_series.json')
        created_query = build_query(series, 'now-1h')
        expected_query = get_json_file('grafana/query_builder/grafana_series_query.json')
        self.assertEqual(expected_query, created_query)
        validate_query(created_query)

    def test_multiple_aggs(self):
        series = get_json_file('grafana/query_builder/grafana_series_terms.json')
        created_query = build_query(series, 'now-100m')
        expected_query = get_json_file('grafana/query_builder/grafana_series_terms_query.json')
        self.assertEqual(expected_query, created_query)
        validate_query(created_query)

    def test_count(self):
        """Count metrics get converted to value_count(timeField)"""
        series = get_json_file('grafana/query_builder/grafana_series_count.json')
        created_query = build_query(series, 'now-3d')
        expected_query = get_json_file('grafana/query_builder/grafana_series_count_query.json')
        self.assertEqual(expected_query, created_query)
        validate_query(created_query)

    def test_multiple_metrics(self):
        series = get_json_file('grafana/query_builder/grafana_multiple_metrics.json')
        created_query = build_query(series, 'now-30m')
        expected_query = get_json_file('grafana/query_builder/grafana_multiple_metrics_query.json')
        self.assertEqual(expected_query, created_query)
        validate_query(created_query)

    def test_no_date_histogram(self):
        series = get_json_file('grafana/query_builder/grafana_no_date_histogram.json')
        with self.assertRaises(ValidationError) as e:
            build_query(series, 'now-30m')
            self.assertEqual(e.exception, 'Dashboard must include a date histogram aggregation.')

    def test_unsupported_aggregation(self):
        series = get_json_file('grafana/query_builder/grafana_geo_hash_grid.json')
        with self.assertRaises(ValidationError) as e:
            build_query(series, 'now-30m')
            self.assertEqual(e.exception, 'geohash_grid aggregation not supported.')


class TestGrafanaTemplating(TestCase):
    def test_templating(self):
        """Test Grafana panel templating handling"""
        templates = get_json_file('grafana/templating/templating_info.json')
        panel_info = get_content('grafana/templating/templating_panel.txt')
        expected_panel = get_content('grafana/templating/templating_panel_final.txt')

        templated_panel = template_response(panel_info, templates)
        self.assertEqual(json.loads(templated_panel), json.loads(expected_panel))

        # Make sure we can make a valid query from the output
        query = build_query(json.loads(str(templated_panel)), 'now-1h')
        validate_query(query)
