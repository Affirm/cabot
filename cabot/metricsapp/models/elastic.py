from django.db import models
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search
import json
import logging
from cabot.metricsapp.api import create_es_client
from .base import MetricsSourceBase, MetricsStatusCheckBase


logger = logging.getLogger(__name__)


class ElasticsearchSource(MetricsSourceBase):
    class Meta:
        app_label = 'metricsapp'

    def __str__(self):
        return self.name

    urls = models.TextField(
        max_length=250,
        null=False,
        help_text='Comma-separated list of Elasticsearch hosts. '
                  'Format: "localhost" or "https://user:secret@localhost:443."'
    )

    _client = None

    @property
    def client(self):
        """
        Return a global elasticsearch-py client for this ESSource (recommended practice
        for elasticsearch-py).
        """
        if self._client:
            return self._client
        return create_es_client(self.urls)


class ElasticsearchStatusCheck(MetricsStatusCheckBase):
    class Meta:
        app_label = 'metricsapp'

    queries = models.TextField(
        max_length=10000,
        help_text='List of raw json Elasticsearch queries. Format: [q] or [q1, q2, ...]. '
                  'Query guidelines: all aggregations should be named "agg." The most '
                  'internal aggregation must be a date_histogram. Metrics names should be '
                  'the same as the metric types (e.g., "max", "min", "avg").'
    )

    def get_series(self):
        """
        Get the relevant data for a check from Elasticsearch and parse it
        into a generic format.
        :param check: the ElasticsearchStatusCheck
        :return data in the format
            status:
            error_message:
            error_code:
            raw:
            data:
              - series: a.b.c.d
                datapoints:
                  - [timestamp, value]
                  - [timestamp, value]
              - series: a.b.c.p.q
                datapoints:
                  - [timestamp, value]
                check:
        """
        parsed_data = dict()
        parsed_data['raw'] = None
        # Will be set to true if we encounter an error
        parsed_data['error'] = False

        try:
            queries = json.loads(self.queries)
        except ValueError as e:
            logger.exception('Error loading Elasticsearch queries: {}'.format(self.queries))
            parsed_data['error_code'] = type(e).__name__
            parsed_data['error_message'] = str(e)
            parsed_data['error'] = True
            return parsed_data

        for query in queries:
            client = ElasticsearchSource.objects.get(name=self.source.name).client
            try:
                search = Search().from_dict(query)
                response = search.using(client).execute()
                parsed_data['raw'] = response.to_dict()
                parsed_data['data'] = self._es_rec([response.to_dict()['aggregations']])
            except Exception as e:
                # TODO: not generic exception
                logger.exception('Error executing Elasticsearch query: {}'.format(query))
                parsed_data['error_code'] = type(e).__name__
                parsed_data['error_message'] = str(e)
                parsed_data['error'] = True
                break

        return parsed_data

    def _es_rec(self, series, series_name=None):
        """
        Look through the json response recursively to go through all the aggregation buckets
        :param series: the aggregations part of the ES response
        :param series_name: the name of the series we're looking at ("key1.key2....metric_name")
        """
        if len(series) == 0:
            return []

        # All aggregations should be named 'agg'
        if series[0].get('agg') is not None:
            data = []
            for subseries in series:
                subseries_name = subseries.get('key')
                # New name is "series_name.subseries_name" (if they exist)
                data += self._es_rec(subseries['agg']['buckets'], '.'.join(filter(lambda x: x,
                                                                                  [series_name, subseries_name])))
            return data

        # If there are no more aggregations, we've reached the metric
        return self._es_base_case(series, series_name)

    def _es_base_case(self, series, series_name):
        """
        Extract the metric name and values from a json series
        :param series: subset of the ES response that includes a list of metric values with
                       date histogram keys
        :param series_name: the name of the series we're looking at
        :return: list of series and datapoints in the format
                 {'series': series_name, 'datapoints': [[timestamp, value], [timestamp, value], ...]
        """
        name_to_series = {}
        for metric_name in series[0]:
            # Not actually a metric name--other fields
            if metric_name in ['key_as_string', 'key', 'doc_count']:
                continue

            elif metric_name in ['min', 'max', 'avg', 'value_count', 'sum', 'cardinality', 'moving_avg', 'derivative']:
                name_to_series[metric_name] = [[bucket['key'], bucket[metric_name]['value']] for bucket in series]

            elif metric_name in ['percentiles']:
                # Create separate series for each percentile
                for metric_subname in series[0][metric_name]['values']:
                    name_to_series[metric_subname] = []
                for bucket in series:
                    timestamp = bucket['key']
                    for metric_subname in bucket[metric_name]['values']:
                        name_to_series[metric_subname].append([timestamp,
                                                               bucket[metric_name]['values'][metric_subname]])

            # Unsupported metrics that are supported in Grafana: raw_document (non-numeric) and extended_stats
            # (too many return values and repeats other metrics).
            else:
                raise NotImplementedError('Elasticsearch metric type not supported: {}'.format(metric_name))

        data = []
        for metric in name_to_series:
            data.append({'series': '.'.join(filter(lambda x: x, [series_name, metric])),
                         'datapoints': name_to_series[metric]})
        return data
