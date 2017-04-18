from elasticsearch import Elasticsearch


def create_es_client(url):
    """
    Create an elasticsearch-py client
    :param url: url string
    :return: a new elasticsearch-py client
    """
    return Elasticsearch([url.strip()])
