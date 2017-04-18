from django import forms
import json
from .grafana import GrafanaStatusCheckForm
from cabot.metricsapp.models import ElasticsearchStatusCheck


class GrafanaElasticsearchStatusCheckForm(GrafanaStatusCheckForm):
    class Meta:
        model = ElasticsearchStatusCheck
        fields = [
            'name',
            'source',
            'queries',
            'check_type',
            'warning_value',
            'high_alert_importance',
            'high_alert_value',
            'frequency',
            'retries',
            'time_range',
            'active',
        ]

    def __init__(self, *args, **kwargs):
        es_fields = kwargs.pop('es_fields')
        super(GrafanaElasticsearchStatusCheckForm, self).__init__(*args, **kwargs)

        self.fields['queries'].initial = json.dumps(es_fields['queries'])
        # Hide queries so users can't edit them
        self.fields['queries'].widget = forms.HiddenInput()
        self.fields['queries'].help_text = None
