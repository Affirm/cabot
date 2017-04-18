from elasticsearch import Elasticsearch


def create_es_client(urls, timeout):
    """
    Create an elasticsearch-py client
    :param url: url string
    :param timeout: timeout for queries to the client
    :return: a new elasticsearch-py client
    """
    urls = [url.strip() for url in urls.split(',')]
    return Elasticsearch(urls, timeout=timeout)
