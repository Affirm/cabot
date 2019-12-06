from django import forms
from django.contrib.auth.models import AnonymousUser

from cabot.cabotapp.views import StatusCheckForm
from cabot.metricsapp.api import get_status_check_fields
from cabot.metricsapp.models import GrafanaInstance, GrafanaDataSource

# Model forms for admin site
from cabot.metricsapp.models.grafana import set_grafana_panel_from_session, GrafanaPanel


class GrafanaInstanceAdminForm(forms.ModelForm):
    class Meta:
        model = GrafanaInstance
        exclude = []


class GrafanaDataSourceAdminForm(forms.ModelForm):
    class Meta:
        model = GrafanaDataSource
        exclude = []


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

    _autofilled_fields = ('time_range', 'check_type', 'warning_value', 'high_alert_value', 'source')
    _disabled_fields = ('source',)

    def __init__(self, grafana_session_data=None, user=None, initial=None, *args, **kwargs):
        self.grafana_panel = ((initial and initial['grafana_panel'])
                              or (kwargs.get('instance') and kwargs['instance'].grafana_panel)
                              or GrafanaPanel())

        if grafana_session_data:
            dashboard_info = grafana_session_data['dashboard_info']
            panel_info = grafana_session_data['panel_info']
            templating_dict = grafana_session_data['templating_dict']
            instance_id = grafana_session_data['instance_id']
            grafana_data_source = GrafanaDataSource.objects.get(
                grafana_source_name=grafana_session_data['datasource'],
                grafana_instance_id=instance_id
            )

            # we will reuse the PK of instance.grafana_panel if there's one set, changes are manually saved in save()
            set_grafana_panel_from_session(self.grafana_panel, grafana_session_data)

            grafana_fields = get_status_check_fields(dashboard_info, panel_info, grafana_data_source,
                                                     templating_dict, self.grafana_panel, user)

            # MetricsSourceBase overrides __unicode__ to return its name, but we need it to serialize to
            # its pk so ModelChoiceForm can handle it right
            grafana_fields['source'] = grafana_fields['source'].pk

            # apply initial on top of get_status_check_fields() to allow overriding
            if initial:
                grafana_fields.update(initial)
            initial = grafana_fields

        super(GrafanaStatusCheckForm, self).__init__(*args, initial=initial, **kwargs)

        self.fields['name'].widget = forms.TextInput(attrs=dict(style='width:50%'))
        self.fields['name'].help_text = None

        for field_name in self._autofilled_fields:
            self.fields[field_name].help_text += ' Autofilled from the Grafana dashboard.'

        for field_name in self._disabled_fields:
            self.fields[field_name].disabled = True

        self.user = user  # used in save(), ignored if None

    def save(self, commit=True):
        model = super(GrafanaStatusCheckForm, self).save(commit=False)

        # the grafana panel may have been created or updated, so also save that
        if self.grafana_panel:
            self.grafana_panel.save()
            model.grafana_panel = self.grafana_panel

        if self.user and not isinstance(self.user, AnonymousUser):
            model.created_by = self.user

        # When commit is False, we just get the model, but the service/instance sets aren't saved
        # (since the model doesn't have a pk yet). Re-run to actually save the service and instance sets
        model = super(GrafanaStatusCheckForm, self).save()

        return model
