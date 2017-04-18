import logging
from collections import defaultdict
from elasticsearch_dsl import Search, A
from elasticsearch_dsl.query import Range
from django.core.exceptions import ValidationError
from cabot.metricsapp.defs import ES_SUPPORTED_METRICS
from .grafana import template_response


logger = logging.getLogger(__name__)


def build_query(series, min_time='now-10m', default_interval='1m'):
    """
    Given series information from the Grafana API, build an Elasticsearch query
    :param series: a "target" in the Grafana dashboard API response
    :param min_time: the earliest time we're looking for
    :return: Elasticsearch query
    """
    search = Search().query('query_string', query=series['query'], analyze_wildcard=True) \
        .query(Range(** {series['timeField']: {'gte': min_time}}))
    search.aggs.bucket('agg', get_aggs(series, min_time, default_interval))
    return search.to_dict()


def get_aggs(series, min_time, default_interval):
    """
    Get the ES aggregations from the input Grafana API series info
    :param series: a "target" in the Grafana dashboard API response
    :return an elasticsearch-dsl "agg" containing all the aggregation info
    """
    aggs = None
    # Variable to chain all the aggregations to. When a new agg is added with .bucket, that
    # agg is returned, so "aggs" will keep track of the first aggregation and "aggs_chain" will
    # keep track of the most recently added one.
    aggs_chain = None
    date_histogram = None

    for agg in series['bucketAggs']:
        # date_histogram must be the final aggregation--save it to add after the other aggregations
        type = agg['type']
        if type == 'date_histogram':
            date_histogram = agg
            continue

        # Add extra settings for "terms" aggregation
        elif type == 'terms':
            settings = get_terms_settings(agg)

            if aggs is None:
                aggs = A({'terms': settings})
                aggs_chain = aggs
            else:
                aggs_chain = aggs_chain.bucket('agg', {'terms': settings})

        # Filter functionality can be accomplished with multiple queries instead
        elif type == 'filter':
            raise ValidationError('Filter aggregation not supported. Please add to the query instead.')

        # Geo hash grid doesn't make much sense for alerting
        else:
            raise ValidationError('{} aggregation not supported.'.format(type))

    if not date_histogram:
        raise ValidationError('Dashboard must include a date histogram aggregation.')

    settings = get_date_histogram_settings(date_histogram, min_time, default_interval)

    if aggs is None:
        aggs = A({'date_histogram': settings})
        aggs_chain = aggs
    else:
        aggs_chain = aggs_chain.bucket('agg', {'date_histogram': settings})

    for metric in series['metrics']:
        metric_type = metric['type']

        # Special case for count--not actually an elasticsearch metric, but supported
        if metric_type not in ES_SUPPORTED_METRICS.union(set(['count'])):
            raise ValidationError('Metric type {} not supported.'.format(metric_type))

        # value_count the time field if count is the metric (since the time field must always be present)
        if metric_type == 'count':
            aggs_chain.metric('value_count', 'value_count', field=series['timeField'])

        # percentiles has an extra setting for percents
        elif metric_type == 'percentiles':
            aggs_chain.metric('percentiles', 'percentiles', field=metric['field'],
                              percents=metric['settings']['percents'])

        else:
            aggs_chain.metric(metric['type'], metric['type'], field=metric['field'])

    return aggs


def get_terms_settings(agg):
    """
    Get the settings for a terms aggregation.
    :param agg: the terms aggregation json data
    :return: dict of {setting_name: setting_value}
    """
    terms_settings = dict(field=agg['field'])

    settings = agg['settings']
    order_by = settings.get('orderBy')
    if order_by:
        terms_settings['order'] = {order_by: settings['order']}

    size = settings.get('size')
    if size and int(size) > 0:
        terms_settings['size'] = int(size)

    min_doc_count = settings.get('min_doc_count')
    if min_doc_count:
        terms_settings['min_doc_count'] = int(min_doc_count)

    return terms_settings


def get_date_histogram_settings(agg, min_time, default_interval):
    """
    Get the settings for a date_histogram aggregation.
    :param agg: the date_histogram aggregation json data
    :return: dict of {setting_name: setting_value}
    """
    interval = agg['settings']['interval']
    if str(interval) == 'auto':
        interval = default_interval

    return dict(field=agg['field'], interval=interval, extended_bounds={'min': min_time, 'max': 'now'})


def create_elasticsearch_templating_dict(dashboard_info):
    """
    Make a dictionary of {template_name: template_value} based on
    the templating section of the Grafana dashboard API response. Change the values
    so that they're in the correct Elasticsearch syntax.
    :param dashboard_info: info from the Grafana dashboard API
    :return: dict of {template_name: template_value} for all templates for this
    dashboard
    """
    templates = {}
    templating_info = dashboard_info['dashboard']['templating']

    # Not all data in the templating section are templates--filter out the ones without current values
    for template in filter(lambda template: template.get('current'), templating_info['list']):
        template_value = template['current']['value']
        template_name = template['name']

        # Template for all values should be "*" in the query
        if '$__all' in template_value:
            templates[template_name] = '*'

        # Multi-valued templates are surrounded by parentheses and combined with OR
        elif isinstance(template_value, list):
            templates[template_name] = '({})'.format(' OR '.join(template_value))

        # Interval can also be automatically set
        elif template_value == '$__auto_interval':
            templates[template_name] = 'auto'

        else:
            templates[template_name] = template_value

    return templates


def get_es_status_check_fields(dashboard_info, panel_info, series_list):
    """
    Get the fields necessary to create an ElasticsearchStatusCheck (that aren't in a generic
    MetricsStatusCheck).
    :param dashboard_info: all info for a dashboard from the Grafana API
    :param panel_info: info about the panel we're alerting off of from the Grafana API
    :param series_list: the series the user selected to use
    :return dictionary of the required ElasticsearchStatusCheck fields (queries)
    """
    fields = defaultdict(list)

    templating_dict = create_elasticsearch_templating_dict(dashboard_info)
    series_list = [s for s in panel_info['targets'] if s['refId'] in series_list]
    min_time = dashboard_info['dashboard']['time']['from']
    interval = panel_info.get('interval')
    if interval is not None:
        # interval can be in format (>1h, <10m, etc.). Get rid of symbols
        templated_interval = str(template_response(interval, templating_dict))
        interval = filter(str.isalnum, templated_interval)

    for series in series_list:
        templated_series = template_response(series, templating_dict)
        if interval is not None and interval != 'auto':
            query = build_query(templated_series, min_time=min_time, default_interval=interval)
        else:
            query = build_query(templated_series, min_time=min_time)

        fields['queries'].append(query)

    return fields
