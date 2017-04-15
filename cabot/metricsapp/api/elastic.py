from elasticsearch import Elasticsearch

def create_es_client(urls):
    """
    Create an elasticsearch-py client
    :param urls: comma-separated string of urls
    :return: a new elasticsearch-py client
    """
    url_list = [url.strip() for url in urls.split(',')]
    return Elasticsearch(url_list, timeout=60)


def validate_query(query):
    """
    Validate that an Elasticsearch query is in the format we want
    (all aggregations named 'agg', 'date_histogram' most internal
    aggregation, other metrics named as their metric type).
    :param query: the raw Elasticsearch query
    """
    while query.get('aggs'):
        query = query['aggs']
        if not query.get('agg'):
            raise ValueError('Elasticsearch query format error: aggregations should be named "agg"')

        query = query['agg']
        if query.get('date_histogram'):
            # If we found a date_histogram the rest of the aggs should be metrics
            if not query.get('aggs'):
                raise ValueError('Elasticsearch query format error: query must include a metric')

            query = query['aggs']
            for metric in query:
                if metric not in ['min', 'max', 'avg', 'value_count', 'sum', 'cardinality',
                                  'moving_avg', 'derivative', 'percentiles']:
                    raise ValueError('Elasticsearch query format error: unsupported metric {}'.format(metric))

                if not query[metric].get(metric):
                    raise ValueError('Elasticsearch query format error: metric name must be the same '
                                     'as the metric type')
            return

    raise ValueError('Elasticsearch query format error: date_histogram must be the innermost'
                     'aggregation (besides metrics)')
