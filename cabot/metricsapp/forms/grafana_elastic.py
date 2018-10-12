from django import forms
import json

from cabot.cabotapp.views import GroupedModelForm
from .grafana import GrafanaStatusCheckForm, GrafanaStatusCheckUpdateForm
from cabot.metricsapp.models import ElasticsearchStatusCheck

_GROUPS = (
    ('Basic', ('name', 'active', 'service_set')),
    ('Thresholds', ('check_type', 'warning_value', 'high_alert_importance', 'high_alert_value')),
    ('Query', ('queries', 'time_range', 'consecutive_failures', 'retries', 'frequency', 'ignore_final_data_point')),
    ('Advanced', ('auto_sync', 'use_activity_counter', 'runbook')),
)


class GrafanaElasticsearchStatusCheckForm(GrafanaStatusCheckForm):
    class Meta(GroupedModelForm.Meta):
        model = ElasticsearchStatusCheck
        grouped_fields = _GROUPS
        widgets = {
            'auto_sync': forms.CheckboxInput()
        }

    def __init__(self, *args, **kwargs):
        es_fields = kwargs.pop('es_fields')
        super(GrafanaElasticsearchStatusCheckForm, self).__init__(*args, **kwargs)

        self.fields['queries'].initial = json.dumps(es_fields['queries'])
        # Hide queries so users can't edit them
        self.fields['queries'].widget = forms.Textarea(attrs=dict(readonly='readonly',
                                                                  style='width:100%'))
        self.fields['queries'].help_text = None


class GrafanaElasticsearchStatusCheckUpdateForm(GrafanaStatusCheckUpdateForm):
    class Meta(GroupedModelForm.Meta):
        model = ElasticsearchStatusCheck
        grouped_fields = _GROUPS
        widgets = {
            'auto_sync': forms.CheckboxInput()
        }

    def __init__(self, *args, **kwargs):
        super(GrafanaElasticsearchStatusCheckUpdateForm, self).__init__(*args, **kwargs)
        self.fields['queries'].widget = forms.Textarea(attrs=dict(readonly='readonly',
                                                                  style='width:100%'))
        self.fields['queries'].help_text = None

    def save(self, commit=True):
        if self.instance.grafana_panel is not None:
            self.instance.grafana_panel.save()

        return super(GrafanaElasticsearchStatusCheckUpdateForm, self).save(commit=commit)
