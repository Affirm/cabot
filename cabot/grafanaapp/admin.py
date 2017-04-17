from django.contrib import admin
from cabot.grafanaapp.forms import GrafanaInstanceForm, GrafanaDataSourceForm
from cabot.grafanaapp.models import GrafanaInstance, GrafanaDataSource


class GrafanaInstanceAdmin(admin.ModelAdmin):
    form = GrafanaInstanceForm


class GrafanaDataSourceAdmin(admin.ModelAdmin):
    form = GrafanaDataSourceForm


admin.site.register(GrafanaInstance, GrafanaInstanceAdmin)
admin.site.register(GrafanaDataSource, GrafanaDataSourceAdmin)
