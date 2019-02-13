# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('cabotapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='GrafanaDataSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('grafana_source_name', models.CharField(help_text=b'The name for a data source in grafana (e.g. metrics-stage")', max_length=30)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='GrafanaInstance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text=b'Unique name for Grafana site.', unique=True, max_length=30)),
                ('url', models.CharField(help_text=b'Url of Grafana site.', max_length=100)),
                ('api_key', models.CharField(help_text=b'Grafana API token for authentication (http://docs.grafana.org/http_api/auth/).', max_length=100)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='GrafanaPanel',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('dashboard_uri', models.CharField(max_length=40)),
                ('panel_id', models.IntegerField()),
                ('series_ids', models.CharField(max_length=50)),
                ('selected_series', models.CharField(max_length=50)),
                ('panel_url', models.CharField(max_length=1024, null=True)),
                ('grafana_instance', models.ForeignKey(to='metricsapp.GrafanaInstance')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MetricsSourceBase',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text=b'Unique name for the data source', unique=True, max_length=30)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ElasticsearchSource',
            fields=[
                ('metricssourcebase_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='metricsapp.MetricsSourceBase')),
                ('urls', models.TextField(help_text=b'Comma-separated list of Elasticsearch hosts. Format: "localhost" or "https://user:secret@localhost:443."', max_length=250)),
                ('index', models.TextField(default=b'*', help_text='Elasticsearch index name. Can include wildcards (&quot;*&quot;) or date math expressions (&quot;&lt;static_name{date_math_expr{date_format|time_zone}}\\&gt;&quot;). For example, an index could be &quot;&lt;metrics-{now/d}&gt;,&lt;metrics-{now/d-1d}&gt;&quot;, resolving to &quot;metrics-yyyy-mm-dd,metrics-yyyy-mm-dd&quot;, for the past 2 days of metrics.', max_length=50)),
                ('timeout', models.IntegerField(default=20, help_text=b'Timeout for queries to this index.')),
                ('max_concurrent_searches', models.IntegerField(default=None, help_text=b'Maximum concurrent searches the multi search api can run.', null=True, blank=True)),
            ],
            options={
            },
            bases=('metricsapp.metricssourcebase',),
        ),
        migrations.CreateModel(
            name='MetricsStatusCheckBase',
            fields=[
                ('statuscheck_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cabotapp.StatusCheck')),
                ('check_type', models.CharField(help_text=b'Comparison operator to use when comparing data point values against a threshold. The check will succeed if the expression "value operator threshold" (e.g. 10 >= 4) is true.', max_length=30, verbose_name=b'Comparison operator', choices=[(b'>', b'Greater than'), (b'>=', b'Greater than or equal'), (b'<', b'Less than'), (b'<=', b'Less than or equal'), (b'==', b'Equal to')])),
                ('warning_value', models.FloatField(help_text=b'Threshold to use for warnings. A check may have a warning threshold, failure threshold, or both.', null=True, verbose_name=b'Warning threshold', blank=True)),
                ('high_alert_importance', models.CharField(default=b'ERROR', help_text=b'Severity level for a failure. Choose "critical" if the alert needs immediate attention, and "error" if you can fix it tomorrow morning.', max_length=30, verbose_name=b'Failure severity', choices=[(b'ERROR', b'Error'), (b'CRITICAL', b'Critical')])),
                ('high_alert_value', models.FloatField(help_text=b'Threshold to use for failures (error or critical). A check may have a warning threshold, failure threshold, or both.', null=True, verbose_name=b'Failure threshold', blank=True)),
                ('time_range', models.IntegerField(default=30, help_text=b'Time range in minutes the check gathers data for.')),
                ('auto_sync', models.NullBooleanField(default=True, help_text=b'For Grafana status checks--should Cabot poll Grafana for dashboard updates and automatically update the check?')),
                ('consecutive_failures', models.PositiveIntegerField(default=1, help_text=b'Number of consecutive data points that must exceed the alert threshold before an alert is triggered. Applies to both warning and high-alert thresholds.', validators=[django.core.validators.MinValueValidator(1)])),
                ('on_empty_series', models.CharField(default=b'fill_zero', help_text=b'Action to take if the series is empty. Options are: pass, warn, or fail immediately, or insert a single data point with value zero.', max_length=16, choices=[(b'pass', b'Pass'), (b'warn', b'Warn'), (b'fail', b'Fail (error/critical)'), (b'fill_zero', b'Fill zero')])),
            ],
            options={
            },
            bases=('cabotapp.statuscheck',),
        ),
        migrations.CreateModel(
            name='ElasticsearchStatusCheck',
            fields=[
                ('metricsstatuscheckbase_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='metricsapp.MetricsStatusCheckBase')),
                ('queries', models.TextField(help_text=b'List of raw json Elasticsearch queries. Format: [q] or [q1, q2, ...]. Query guidelines: all aggregations should be named "agg." The most internal aggregation must be a date_histogram. Metrics names should be the same as the metric types (e.g., "max", "min", "avg").', max_length=10000)),
                ('ignore_final_data_point', models.BooleanField(default=True, help_text=b'True to skip the final data point when calculating status for this check (since the data point is a partial bucket which may be incomplete and have skewed data). False to use all data points.')),
            ],
            options={
            },
            bases=('metricsapp.metricsstatuscheckbase',),
        ),
        migrations.AddField(
            model_name='metricsstatuscheckbase',
            name='grafana_panel',
            field=models.ForeignKey(to='metricsapp.GrafanaPanel', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='metricsstatuscheckbase',
            name='source',
            field=models.ForeignKey(to='metricsapp.MetricsSourceBase'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='grafanainstance',
            name='sources',
            field=models.ManyToManyField(help_text=b'Metrics sources used by this Grafana site.', to='metricsapp.MetricsSourceBase', through='metricsapp.GrafanaDataSource'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='grafanadatasource',
            name='grafana_instance',
            field=models.ForeignKey(to='metricsapp.GrafanaInstance'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='grafanadatasource',
            name='metrics_source_base',
            field=models.ForeignKey(to='metricsapp.MetricsSourceBase'),
            preserve_default=True,
        ),
    ]
