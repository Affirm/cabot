import boto3
from datetime import datetime, timedelta
import json
import logging


def _get_boto_client():
    """
    Get boto client from cloudwatch
    :return: nothing
    """
    logging.info('making a client')
    #return boto3.client('cloudwatch')
    return None


def _convert_cloudwatch_to_graphite(json_resp, namespace):
    """
    Covert the cloudwatch response into graphite compatible output
    TODO: better generic format
    :param resp: cloudwatch response
    :return: graphite-style output
    """
    data = []
    for datapoint in json_resp['Datapoints']:
        value = datapoint['Average']
        dt = datapoint['Timestamp']
        ts = int((dt - datetime(1970, 1, 1)).total_seconds())
        data.append([value, ts])

    output = json.loads({
        'target': namespace,
        'datapoints': data,
    })
    return [output]

def cloudwatch_parse_metric(namespace, metric_name, dimension_name, dimension_value,
                 granularity, statistic):
    _boto_client = _get_boto_client()
    logging.info("made boto client")

    if _boto_client is None:
        logging.exception('No boto client found.')
        # TODO: return what??
        return

    try:
        resp = _boto_client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=[
                {
                    'Name': dimension_name,
                    'Value': dimension_value
                }
            ],
            StartTime=datetime.utcnow() - timedelta(seconds=granularity),
            EndTime=datetime.utcnow(),
            Period=granularity,
            Statistic=statistic
        )
        logging.info(resp)
        return _convert_cloudwatch_to_graphite(json.loads(resp), namespace)
    except Exception as e:
        # todo: gonna change this a lot probs
        logging.exception("Boto get didn't work %s" % e)