from django.contrib import admin
from cabot.metricsapp.models import ElasticsearchSource, ElasticsearchStatusCheck, \
    GrafanaDataSource, GrafanaInstance
from cabot.metricsapp.forms import ElasticsearchSourceForm, ElasticsearchStatusCheckForm, \
    GrafanaDataSourceForm, GrafanaInstanceForm


class ElasticsearchSourceAdmin(admin.ModelAdmin):
    form = ElasticsearchSourceForm


class ElasticsearchStatusCheckAdmin(admin.ModelAdmin):
    form = ElasticsearchStatusCheckForm


class GrafanaInstanceAdmin(admin.ModelAdmin):
    form = GrafanaInstanceForm


class GrafanaDataSourceAdmin(admin.ModelAdmin):
    form = GrafanaDataSourceForm


admin.site.register(ElasticsearchSource, ElasticsearchSourceAdmin)
admin.site.register(ElasticsearchStatusCheck, ElasticsearchStatusCheckAdmin)
admin.site.register(GrafanaDataSource, GrafanaDataSourceAdmin)
admin.site.register(GrafanaInstance, GrafanaInstanceAdmin)
