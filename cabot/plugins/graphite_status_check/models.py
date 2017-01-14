from cabot.cabotapp.models import StatusCheck, StatusCheckResult
from .influx import parse_metric

from celery.utils.log import get_task_logger
import json
import time


logger = get_task_logger(__name__)

class GraphiteStatusCheck(StatusCheck):
    """
    Uses influx, not graphite
    """

    class Meta(StatusCheck.Meta):
        proxy = True
        verbose_name = "graphitestatuscheck"

    @property
    def check_category(self):
        return "Metric check"

    def format_error_message(self, failure_value, actual_hosts,
                             actual_metrics, name):
        """
        A summary of why the check is failing for inclusion in short
        alert messages

        Returns something like:
        "5.0 > 4 | 1/2 hosts"
        """
        hosts_string = u''
        if self.expected_num_hosts > 0:
            hosts_string = u' | %s/%s hosts' % (actual_hosts,
                                                self.expected_num_hosts)
            if self.expected_num_hosts > actual_hosts:
                return u'Hosts missing%s' % hosts_string
        if self.expected_num_metrics > 0:
            metrics_string = u'%s | %s/%s metrics' % (name,
                                                actual_metrics,
                                                self.expected_num_metrics)
            if self.expected_num_metrics > actual_metrics:
                return u'Metrics condition missed for %s' % metrics_string
        if failure_value is None:
            return "Failed to get metric from Graphite"
        return u"%0.1f %s %0.1f%s" % (
            failure_value,
            self.check_type,
            float(self.value),
            hosts_string
        )

    def _run(self):
        series = parse_metric(self.metric,
                              selector=self.metric_selector,
                              group_by=self.group_by,
                              fill_empty=self.fill_empty,
                              where_clause=self.where_clause,
                              time_delta=self.interval * 6)

        result = StatusCheckResult(
            check=self,
        )

        if series['error']:
            result.succeeded = False
            result.error = 'Error fetching metric from source'
            return result
        else:
            failed = None

        # Add a threshold in the graph
        threshold = None
        if series['raw'] and series['raw'][0]['datapoints']:
            start = series['raw'][0]['datapoints'][0]
            end = series['raw'][0]['datapoints'][-1]
            threshold = dict(target='alert.threshold',
                             datapoints=[(self.value, start[1]),
                                         (self.value, end[1])])

        failure_value = 0
        failed_metric_name = None
        matched_metrics = 0

        # First do some crazy average checks (if we expect more than 1 metric)
        if series['num_series_with_data'] > 0:
            result.average_value = series['average_value']
            if self.check_type == '<':
                failed = not float(series['min']) < float(self.value)
                if failed:
                    failure_value = series['min']
            elif self.check_type == '<=':
                failed = not float(series['min']) <= float(self.value)
                if failed:
                    failure_value = series['min']
            elif self.check_type == '>':
                failed = not float(series['max']) > float(self.value)
                if failed:
                    failure_value = series['max']
            elif self.check_type == '>=':
                failed = not float(series['max']) >= float(self.value)
                if failed:
                    failure_value = series['max']
            elif self.check_type == '==':
                failed = not float(self.value) in series['all_values']
                if failed:
                    failure_value = float(self.value)
            else:
                raise Exception(u'Check type %s not supported' %
                                self.check_type)

        if series['num_series_with_data'] < self.expected_num_hosts:
            failed = True

        reference_point = time.time() - ((self.interval + 2) * 60)

        if self.expected_num_metrics > 0:
            json_series = series['raw']
            logger.info("Processing series " + str(json_series))
            for line in json_series:
                matched_metrics = 0
                metric_failed = True

                for point in line['datapoints']:

                    last_value = point[0]
                    time_stamp = point[1]

                    if time_stamp <= reference_point:
                        logger.debug('Point %s is older than ref ts %d' % \
                            (str(point), reference_point))
                        continue

                    if last_value is not None:
                        if self.check_type == '<':
                            metric_failed = not last_value < float(self.value)
                        elif self.check_type == '<=':
                            metric_failed = not last_value <= float(self.value)
                        elif self.check_type == '>':
                            metric_failed = not last_value > float(self.value)
                        elif self.check_type == '>=':
                            metric_failed = not last_value >= float(self.value)
                        elif self.check_type == '==':
                            metric_failed = not last_value == float(self.value)
                        else:
                            raise Exception(u'Check type %s not supported' %
                                            self.check_type)
                        if metric_failed:
                            failure_value = last_value
                            failed_metric_name = line['target']
                        else:
                            matched_metrics += 1
                            logger.info("Metrics matched: " + str(matched_metrics))
                            logger.info("Required metrics: " + str(self.expected_num_metrics))
                    else:
                        failed = True

                logger.info("Processing series ...")

                if matched_metrics < self.expected_num_metrics:
                    failed = True
                    failure_value = None
                    failed_metric_name = line['target']
                    break
                else:
                    failed = False

        try:
            if threshold is not None:
                series['raw'].append(threshold)
            result.raw_data = json.dumps(series['raw'], indent=2)
        except:
            result.raw_data = series['raw']
        result.succeeded = not failed

        if not result.succeeded:
            result.error = self.format_error_message(
                failure_value,
                series['num_series_with_data'],
                matched_metrics,
                failed_metric_name,
            )

        result.actual_hosts = series['num_series_with_data']
        result.actual_metrics = matched_metrics
        result.failure_value = failure_value
        return result
