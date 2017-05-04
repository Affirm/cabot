import logging
from elasticsearch_dsl import Search, A
from elasticsearch_dsl.query import Range
from django.core.exceptions import ValidationError
from cabot.metricsapp.defs import ES_SUPPORTED_METRICS


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
    search.aggs.bucket('agg', get_aggs(series, default_interval))
    return search.to_dict()


def get_aggs(series, default_interval):
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

    settings = get_date_histogram_settings(date_histogram, default_interval)
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


def get_date_histogram_settings(agg, default_interval):
    """
    Get the settings for a date_histogram aggregation.
    :param agg: the date_histogram aggregation json data
    :return: dict of {setting_name: setting_value}
    """
    interval = agg['settings']['interval']
    if interval == 'auto':
        interval = default_interval

    return dict(field=agg['field'], interval=interval)


def template_response(grafana_api_data, templating_info):
    """
    Change the panel info from the Grafana dashboard API response
    based on the dashboard templates
    :param grafana_data: any string portion of the response from the Grafana API
    :param templating_info: "templating" section from the Grafana dashboard API
    :return: panel_info with all templating values filled in
    """
    templates = create_templating_dict(templating_info)

    # Loop through all the templates and replace them if they're used in this panel
    for template in templates:
        grafana_api_data = grafana_api_data.replace('${}'.format(template), templates[template])

    return grafana_api_data


def create_templating_dict(templating_info):
    """
    Make a dictionary of {template_name: template_value} based on
    the templating section of the Grafana dashboard API response. Change the values
    so that they're in the correct Elasticsearch syntax.
    :param templating_info: "templating" section from the Grafana dashboard API
    :return: dict of {template_name: template_value} for all templates for this
    dashboard
    """
    templates = {}

    for template in templating_info['list']:
        # Not all fields in the templating sections are actual templates
        current_templates = template.get('current')
        if not current_templates:
            continue

        template_value = current_templates['value']
        template_name = template['name']

        # Template for all values should be "*" in the query
        if template_value == '$__all':
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
