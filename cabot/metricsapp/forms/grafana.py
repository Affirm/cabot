from django import forms
from django.contrib.auth.models import AnonymousUser

from cabot.cabotapp.views import StatusCheckForm
from cabot.metricsapp.models import GrafanaInstance, GrafanaDataSource


# Model forms for admin site
class GrafanaInstanceAdminForm(forms.ModelForm):
    class Meta:
        model = GrafanaInstance


class GrafanaDataSourceAdminForm(forms.ModelForm):
    class Meta:
        model = GrafanaDataSource


# Forms for selecting Grafana instance, dashboard, panel, etc.
class GrafanaInstanceForm(forms.Form):
    """Select a Grafana instance to use for a status check"""
    grafana_instance = forms.ModelChoiceField(
        queryset=GrafanaInstance.objects.all(),
        initial=1,
        help_text='Grafana site instance to select a dashboard from.'
    )

    def __init__(self, *args, **kwargs):
        default_grafana_instance = kwargs.pop('default_grafana_instance')
        super(GrafanaInstanceForm, self).__init__(*args, **kwargs)
        if default_grafana_instance is not None:
            self.fields['grafana_instance'].initial = default_grafana_instance


class GrafanaDashboardForm(forms.Form):
    """Select a Grafana dashboard to use for a status check"""
    def __init__(self, *args, **kwargs):
        dashboards = kwargs.pop('dashboards')
        default_dashboard = kwargs.pop('default_dashboard')
        super(GrafanaDashboardForm, self).__init__(*args, **kwargs)

        self.fields['dashboard'] = forms.ChoiceField(
            choices=dashboards,
            help_text='Grafana dashboard to use for the check.'
        )

        if default_dashboard is not None:
            self.fields['dashboard'].initial = default_dashboard


class GrafanaPanelForm(forms.Form):
    """Select a Grafana panel to use for a status check"""
    def __init__(self, *args, **kwargs):
        panels = kwargs.pop('panels')
        default_panel_id = kwargs.pop('default_panel_id')
        super(GrafanaPanelForm, self).__init__(*args, **kwargs)

        self.fields['panel'] = forms.ChoiceField(
            choices=panels,
            help_text='Grafana panel to use for the check.'
        )

        if default_panel_id is not None:
            for panel in panels:
                panel_data = panel[0]
                if panel_data['panel_id'] == default_panel_id:
                    self.fields['panel'].initial = panel_data
                    break

    def clean_panel(self):
        """Make sure the data source for the panel is supported"""
        panel = eval(self.cleaned_data['panel'])
        datasource = panel['datasource']
        grafana_instance_id = panel['grafana_instance_id']

        try:
            GrafanaDataSource.objects.get(grafana_source_name=datasource,
                                          grafana_instance_id=grafana_instance_id)

        except GrafanaDataSource.DoesNotExist:
            raise forms.ValidationError('No matching data source for {}.'.format(datasource))

        return panel


class GrafanaSeriesForm(forms.Form):
    """Select the series to use for a status check"""
    def __init__(self, *args, **kwargs):
        series = kwargs.pop('series')
        default_series = kwargs.pop('default_series')
        super(GrafanaSeriesForm, self).__init__(*args, **kwargs)

        self.fields['series'] = forms.MultipleChoiceField(
            choices=series,
            widget=forms.CheckboxSelectMultiple,
            help_text='Data series to use in the check.'
        )

        if default_series is not None:
            self.fields['series'].initial = default_series

    def clean_series(self):
        """Make sure at least one series is selected."""
        series = self.cleaned_data.get('series')
        if not series:
            raise forms.ValidationError('At least one series must be selected.')

        return series


class GrafanaStatusCheckForm(StatusCheckForm):
    """Generic form for creating a status check. Other metrics sources will subclass this."""
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields')
        super(GrafanaStatusCheckForm, self).__init__(*args, **kwargs)

        self.fields['name'].initial = fields['name']
        self.fields['name'].widget = forms.TextInput(attrs=dict(style='width:50%'))
        self.fields['name'].help_text = None

        # Time range, check_type, and thresholds are editable.
        for field_name in ['time_range', 'check_type', 'warning_value', 'high_alert_value']:
            field_value = fields.get(field_name)
            if field_value is not None:
                self.fields[field_name].initial = field_value
                self.fields[field_name].help_text += ' Autofilled from the Grafana dashboard.'

        # Store fields that will be set in save()
        self.source = fields['source']
        self.grafana_panel = fields['grafana_panel']
        self.user = fields['user']

    # TODO should probably take commit as an argument here
    def save(self):
        # set the MetricsSourceBase here so we don't have to display it
        model = super(GrafanaStatusCheckForm, self).save(commit=False)

        # the grafana panel may have updated as well, so also save that
        self.grafana_panel.save()

        model.source = self.source
        model.grafana_panel = self.grafana_panel
        if self.user is not None and not isinstance(self.user, AnonymousUser):
            model.created_by = self.user

        model.save()

        # When commit is False, we just get the model, but the service/instance sets aren't saved
        # (since the model doesn't have a pk yet). Re-run to actually save the service and instance sets
        model = super(GrafanaStatusCheckForm, self).save()

        return model


class GrafanaStatusCheckUpdateForm(StatusCheckForm):
    """Update a status check created from Grafana"""
    def __init__(self, *args, **kwargs):
        super(GrafanaStatusCheckUpdateForm, self).__init__(*args, **kwargs)
        # Hide name field
        self.fields['name'].widget = forms.TextInput(attrs=dict(style='width:50%'))
