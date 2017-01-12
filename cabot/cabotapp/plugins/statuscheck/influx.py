from .graphite import GraphiteStatusCheck

class InfluxDBStatusCheck(GraphiteStatusCheck):
    class Meta(GraphiteStatusCheck.Meta):
        proxy = True

