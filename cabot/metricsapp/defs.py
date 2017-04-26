# Single metrics return only one value, which will be under "value" in the 
# response from Elasticsearch
ES_METRICS_SINGLE = set(['min', 'max', 'avg', 'value_count', 'sum', 'cardinality', 'moving_avg', 'derivative'])
# Multiple metrics return multiple values (for example, 95th and 99th percentiles, 
# which will be under "values" in the response from Elasticsearch
ES_METRICS_MULTIPLE = set(['percentiles'])
ES_METRICS_ALL = ES_METRICS_SINGLE.union(ES_METRICS_MULTIPLE)

ES_VALIDATION_MSG_PREFIX = 'Elasticsearch query format error'

