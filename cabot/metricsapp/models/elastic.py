import json
import logging
import time
from django.db import models
from django.core.exceptions import ValidationError
from elasticsearch_dsl import Search
from cabot.metricsapp.api import create_es_client, SupportedMetrics, validate_query
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
    index = models.TextField(
        max_length=50,
        default='*',
        help_text='Elasticsearch index name. Can include wildcards (*)',
    )
    index = models.TextField(
        max_length=50,
        default='*',
        help_text='Elasticsearch index name. Can include wildcards (*)',
    )
    timeout = models.IntegerField(
        default=60,
        help_text='Timeout for queries to this index.'
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
        return create_es_client(self.urls, self.timeout)


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

    def clean(self, *args, **kwargs):
        """Validate the query on save"""
        try:
            queries = json.loads(self.queries)
        except ValueError:
            raise ValidationError('Queries are not json-parsable')

        for query in queries:
            validate_query(query)


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
        parsed_data['data'] = []

        for query in json.loads(self.queries):
            source = ElasticsearchSource.objects.get(name=self.source.name)
            try:
                search = Search().from_dict(query)
                response = search.using(source.client).index(source.index).execute()
                parsed_data['raw'] = response.to_dict()
                parsed_data['data'].extend(self._es_rec([response.to_dict()['aggregations']]))
            except Exception as e:
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

        # All aggregations should be named 'agg' (validated in validate_query())
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
        earliest_point = time.time() - self.time_range * 60
        for metric_name in series[0]:
            # Not actually a metric name--other fields
            if metric_name in ['key_as_string', 'key', 'doc_count']:
                continue

            elif metric_name in SupportedMetrics.METRICS_SINGLE.value:
                # Convert ms to seconds and check if they're within the specified time range
                name_to_series[metric_name] = [[bucket['key'] / 1000, bucket[metric_name]['value']]
                                               for bucket in series if bucket['key'] / 1000 > earliest_point]

            elif metric_name in SupportedMetrics.METRICS_MULTIPLE.value:
                # Create separate series for each percentile
                for metric_subname in series[0][metric_name]['values']:
                    name_to_series[metric_subname] = []
                for bucket in series:
                    timestamp = bucket['key'] / 1000
                    if timestamp > earliest_point:
                        for metric_subname in bucket[metric_name]['values']:
                            name_to_series[metric_subname].append([timestamp,
                                                                   bucket[metric_name]['values'][metric_subname]])

            # Unsupported metrics that are supported in Grafana: raw_document (non-numeric) and extended_stats
            # (many return values, which doesn't make sense for a single check, and repeats other metrics).
            else:
                raise NotImplementedError('Elasticsearch metric type not supported: {}'.format(metric_name))

        data = []
        for metric in name_to_series:
            data.append({'series': '.'.join(filter(lambda x: x, [series_name, metric])),
                         'datapoints': name_to_series[metric]})
        return data
