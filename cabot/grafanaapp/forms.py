from django.forms import ModelForm
from cabot.grafanaapp.models import GrafanaInstance, GrafanaDataSource


class GrafanaInstanceForm(ModelForm):
    class Meta:
        model = GrafanaInstance


class GrafanaDataSourceForm(ModelForm):
    class Meta:
        model = GrafanaDataSource