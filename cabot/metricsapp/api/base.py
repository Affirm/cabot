from celery.utils.log import get_task_logger
import json
import time
import copy
from cabot.cabotapp.models import Service, StatusCheckResult
import cabot.metricsapp.defs as defs


logger = get_task_logger(__name__)


def _get_error_message(check, threshold, importance, series_name, value):
    """
    Construct a check's error message, which will differ based on the number of
    consecutive failed points.

    For a single failed point:

        Format:   <importance> <series_name>: <value> not <comparator> <threshold>
        Example:  WARNING foo.service.errors: 100 not < 50

    For N consecutive failed points:

        Format:   <importance> <series_name>: <N> consecutive points not <comparator> <threshold>
        Example:  CRITICAL foo.service.errors: 10 consecutive points not < 50

    """
    if check.consecutive_failures == 1:
        fmt = u'{} {}: {:0.1f} not {} {:0.1f}'
        return fmt.format(importance, series_name, value, check.check_type, threshold)
    else:
        fmt = u'{} {}: {} consecutive points not {} {:0.1f}'
        return fmt.format(importance, series_name, check.consecutive_failures,
                          check.check_type, threshold)


def _point_failure_check(check_type, threshold, value):
    """
    Check whether a point fails the check.
    :param check_type: the type of status check (<, >, etc.)
    :param threshold: the failure threshold value
    :param value: the value we're checking success/failure for
    :return: True if the check fails, False if it succeeds
    """
    if check_type == '<':
        return not value < threshold
    elif check_type == '<=':
        return not value <= threshold
    elif check_type == '>':
        return not value > threshold
    elif check_type == '>=':
        return not value >= threshold
    elif check_type == '==':
        return not value == threshold
    else:
        raise ValueError(u'Check type {} not supported'.format(check_type))


def _get_raw_data_with_thresholds(check, series):
    """
    Return the series data with thresholds added. This function does NOT modify
    the `check` or `series` parameters.
    :param check: the status check
    :param series: the data series
    :return: the data series with high alert/warning thresholds
    """
    first_series_data = series.get('data')[0].get('datapoints')
    if first_series_data:
        start_time, _ = first_series_data[0]
        end_time, _ = first_series_data[-1]

        # Do a deepcopy of the series data intead of modifying it. This is safer
        # as it doesn't risk updating the series data while we're checking it
        # for errors.
        series_data = copy.deepcopy(series['data'])

        # Add threshold line(s) for the graph
        if check.warning_value is not None:
            points = [[start_time, check.warning_value], [end_time, check.warning_value]]
            series_data.append(dict(series='alert.warning_threshold', datapoints=points))

        if check.high_alert_value is not None:
            points = [[start_time, check.high_alert_value], [end_time, check.high_alert_value]]
            series_data.append(dict(series='alert.high_alert_threshold', datapoints=points))

    # Return the series data, as a JSON string
    try:
        return json.dumps(series_data, indent=2)
    except TypeError:
        logger.exception('Error when serializing series to json. Series: {}'.format(series))
        return series_data


def _point_triggering_alert(datapoints, check_type, min_consecutive_failures, threshold):
    if threshold is None:
        return None

    consecutive_failures = 0
    for point in datapoints:
        timestamp, value = point
        if _point_failure_check(check_type, threshold, value):
            consecutive_failures += 1
            if consecutive_failures >= min_consecutive_failures:
                return point
        else:
            consecutive_failures = 0

    return None


def run_metrics_check(check):
    """
    Run the status check.
    :param check: the status check
    :return: a StatusCheckResult containing success/failure/error information
    """
    # Get the series data. If there was an error, return immediately.
    series = check.get_series()

    # If there was an error fetching metrics, fail
    if series['error'] is True:
        message = series.get('error_message')
        logger.exception('Error fetching metrics: {}: {}'.format(series.get('error_code'), message))
        error = 'Error fetching metric from source: {}'.format(message)
        return StatusCheckResult(check=check, succeeded=False, error=error), ['fetch_error']

    # If the series is empty, apply the empty-series handler
    if series['data'] == []:
        if check.on_empty_series == defs.ON_EMPTY_SERIES_PASS:
            return StatusCheckResult(check=check, succeeded=True, error='SUCCESS: no data'), []
        if check.on_empty_series == defs.ON_EMPTY_SERIES_WARN:
            check.importance = Service.WARNING_STATUS
            return StatusCheckResult(check=check, succeeded=False, error='WARNING: no data'), ['warning:no data']
        if check.on_empty_series == defs.ON_EMPTY_SERIES_FAIL:
            check.importance = check.high_alert_importance
            tags = ['{}:no data'.format(check.importance.lower())]
            return StatusCheckResult(check=check, succeeded=False, error='{}: no data'.format(check.importance)), tags

    # Ignore all checks before the following start time
    start_time = time.time() - check.time_range * 60

    def filter_old_points(p):
        timestamp = p[0]
        if timestamp <= start_time:
            logger.debug('Ignoring point {} older than {}'.format(str(p), str(start_time)))
            return False
        return True

    parsed_series = series['data']
    logger.info('Processing series {}'.format(str(parsed_series)))

    # order is important - most severe first, since we report the first error found
    thresholds = [
        (check.high_alert_importance, check.high_alert_value),
        (Service.WARNING_STATUS, check.warning_value),
    ]

    # Process each series, updating result and tags as we go
    result = StatusCheckResult(check=check, succeeded=True)
    result.raw_data = _get_raw_data_with_thresholds(check, series)
    tags = []

    # loop order is:
    #   (high_importance, series_1), (high_importance, series_2), ...,
    #   (warning, series_1), (warning, series_2), ...
    # and we report the first error encountered as our error
    # (but continue looping so we accumulate tags)
    for importance, threshold in thresholds:
        for series_data in parsed_series:
            series_name = series_data['series']
            datapoints = list(filter(filter_old_points, series_data['datapoints']))
            failing_point = _point_triggering_alert(datapoints, check.check_type, check.consecutive_failures, threshold)
            if failing_point is not None:
                tags.append(str(importance.lower()) + ':' + series_name)
                if result.succeeded:
                    # record the first, most severe failure
                    result.succeeded = False
                    check.importance = importance
                    result.error = _get_error_message(check, threshold, importance, series_name, failing_point[1])

        logger.info('Finished processing series {}'.format(series_name))

    return result, tags
