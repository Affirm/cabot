from django import forms
from cabot.cabotapp.views import StatusCheckForm
from cabot.metricsapp.models import GrafanaInstance, GrafanaDataSource


# Model forms for admin site
class GrafanaInstanceForm(forms.ModelForm):
    class Meta:
        model = GrafanaInstance


class GrafanaDataSourceForm(forms.ModelForm):
    class Meta:
        model = GrafanaDataSource


# Forms for selecting Grafana instance, dashboard, panel, etc.
class GrafanaInstanceSelectForm(forms.Form):
    """Select a Grafana instance to use for a status check"""
    grafana_instance = forms.ModelChoiceField(
        queryset=GrafanaInstance.objects.all(),
        initial=1,
        help_text='Grafana site instance to select a dashboard from.'
    )


class GrafanaDashboardForm(forms.Form):
    """Select a Grafana dashboard to use for a status check"""
    def __init__(self, *args, **kwargs):
        dashboards = kwargs.pop('dashboards')
        super(GrafanaDashboardForm, self).__init__(*args, **kwargs)

        self.fields['dashboard'] = forms.ChoiceField(
            choices=dashboards,
            help_text='Grafana dashboard to select a panel from.'
        )


class GrafanaPanelForm(forms.Form):
    """Select a Grafana panel to use for a status check"""
    def __init__(self, *args, **kwargs):
        panels = kwargs.pop('panels')
        super(GrafanaPanelForm, self).__init__(*args, **kwargs)

        self.fields['panel'] = forms.ChoiceField(
            choices=panels,
            help_text='Grafana panel to use for the check.'
        )

    def clean_panel(self):
        """Make sure the data source for the panel is supported"""
        panel = eval(self.cleaned_data['panel'])
        datasource = panel['datasource']

        try:
            GrafanaDataSource.objects.get(grafana_source_name=datasource)
        except GrafanaDataSource.DoesNotExist:
            raise forms.ValidationError('No matching data source for {}.'.format(datasource))

        return panel


class GrafanaSeriesForm(forms.Form):
    """Select the series to use for a status check"""
    def __init__(self, *args, **kwargs):
        series = kwargs.pop('series')
        super(GrafanaSeriesForm, self).__init__(*args, **kwargs)

        self.fields['series'] = forms.MultipleChoiceField(
            choices=series,
            widget=forms.CheckboxSelectMultiple,
            help_text='Data series to use in the check.'
        )

    def clean_series(self):
        """Make sure at least one series is selected."""
        series = self.cleaned_data.get('series')
        if not series:
            raise forms.ValidationError('At least one series must be selected.')

        return series


class GrafanaStatusCheckForm(StatusCheckForm):
    """Generic form for creating a status check. Other metrics sources will subclass"""
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields')
        super(GrafanaStatusCheckForm, self).__init__(*args, **kwargs)

        self.fields['name'].initial = fields['name']
        self.fields['source'].initial = GrafanaDataSource.objects.get(
            grafana_source_name=fields['source_info']['grafana_source_name'],
            grafana_instance=GrafanaInstance.objects.get(id=fields['source_info']['grafana_instance_id'])
        ).metrics_source_base

        # Hide name and source fields so users can't edit them.
        self.fields['name'].widget = forms.HiddenInput()
        self.fields['name'].help_text = None
        self.fields['source'].widget = forms.HiddenInput()
        self.fields['source'].help_text = None

        # Time range and thresholds are editable.
        time_range = fields.get('time_range')
        if time_range is not None:
            self.fields['time_range'].initial = fields['time_range']
            self.fields['time_range'].help_text += ' Autofilled from the dashboard time range in Grafana.'

        thresholds = fields.get('thresholds')
        if thresholds != []:
            # TODO: figure out how to switch min/max for different check types
            self.fields['warning_value'].initial = float(min(thresholds))
            self.fields['warning_value'].help_text += ' Autofilled from the lowest threshold in the Grafana graph.'
            self.fields['high_alert_value'].initial = float(max(thresholds))
            self.fields['high_alert_value'].help_text += ' Autofilled from the highest threshold in the Grafana graph.'
