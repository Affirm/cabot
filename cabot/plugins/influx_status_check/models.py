from cabot.plugins.graphite_status_check.models import GraphiteStatusCheck

class InfluxDBStatusCheck(GraphiteStatusCheck):
    class Meta(GraphiteStatusCheck.Meta):
        proxy = True
        verbose_name = "influxdbstatuscheck"

