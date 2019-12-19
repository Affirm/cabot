from django import forms
import json

from cabot.cabotapp.views import GroupedModelForm
from cabot.metricsapp.api import get_es_status_check_fields
from .grafana import GrafanaStatusCheckForm
from cabot.metricsapp.models import ElasticsearchStatusCheck

_GROUPS = (
    ('Basic', (
        'name',
        'active',
        'service_set',
    )),
    ('Thresholds', (
        'check_type',
        'warning_value',
        'high_alert_importance',
        'high_alert_value',
    )),
    ('Query', (
        'queries',
        'source',
        'time_range',
        'consecutive_failures',
        'retries',
        'frequency',
        'ignore_final_data_point',
        'on_empty_series',
    )),
    ('Advanced', (
        'auto_sync',
        'use_activity_counter',
        'run_delay',
        'run_window',
        'runbook',
    )),
)


class GrafanaElasticsearchStatusCheckForm(GrafanaStatusCheckForm):
    class Meta(GroupedModelForm.Meta):
        model = ElasticsearchStatusCheck
        grouped_fields = _GROUPS
        widgets = {
            'auto_sync': forms.CheckboxInput()
        }

    _autofilled_fields = GrafanaStatusCheckForm._autofilled_fields + ('queries',)
    _disabled_fields = GrafanaStatusCheckForm._disabled_fields + ('queries',)

    def __init__(self, grafana_session_data=None, initial=None, *args, **kwargs):
        if grafana_session_data:
            dashboard_info = grafana_session_data['dashboard_info']
            panel_info = grafana_session_data['panel_info']
            series = grafana_session_data['series']

            es_fields = get_es_status_check_fields(dashboard_info, panel_info, series)
            es_fields['queries'] = json.dumps(es_fields['queries'])  # TODO necessary?

            if initial:
                es_fields.update(initial)
            initial = es_fields

        super(GrafanaElasticsearchStatusCheckForm, self).__init__(*args, initial=initial,
                                                                  grafana_session_data=grafana_session_data, **kwargs)

        # styling
        self.fields['queries'].widget.attrs['style'] = 'width:75%'
        self.fields['queries'].help_text = None
