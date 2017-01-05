import boto3
import logging


_boto_client = None

def _get_boto_client():
    """
    Get boto client from cloudwatch
    :return: nothing
    """
    global _boto_client
    _boto_client = boto3.client('cloudwatch')


def cloudwatch_parse_metric(namespace, metric_name, dimension_name,
                            dimension_value, granularity, statistic,
                            percentile):
    pass