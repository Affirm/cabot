# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import cabot.cabotapp.fields
from django.conf import settings
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityCounter',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('count', models.PositiveIntegerField(default=0)),
                ('last_enabled', models.DateTimeField(null=True)),
                ('last_disabled', models.DateTimeField(null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AlertPlugin',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(unique=True, max_length=30, editable=False)),
                ('enabled', models.BooleanField(default=True)),
                ('polymorphic_ctype', models.ForeignKey(related_name='polymorphic_cabotapp.alertplugin_set', editable=False, to='contenttypes.ContentType', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AlertPluginUserData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=30, editable=False)),
                ('polymorphic_ctype', models.ForeignKey(related_name='polymorphic_cabotapp.alertpluginuserdata_set', editable=False, to='contenttypes.ContentType', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='HipchatInstance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text=b'Unique name for the Hipchat server.', unique=True, max_length=20)),
                ('server_url', models.CharField(help_text=b'Url for the Hipchat server.', max_length=100)),
                ('api_v2_key', models.CharField(help_text=b'API V2 key that will be used for sending alerts.', max_length=50)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MatterMostInstance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text=b'Unique name for the Mattermost server.', unique=True, max_length=20)),
                ('server_url', models.CharField(help_text=b'Base url for the Mattermost server.', max_length=100)),
                ('api_token', models.CharField(help_text=b'API token that will be used for sending alerts.', max_length=100)),
                ('webhook_url', models.CharField(help_text=b'System generated URL for webhook integrations', max_length=256)),
                ('default_channel_id', models.CharField(help_text=b'Default channel ID to use if a service does not have one set. If blank, services with no channel ID set will log an error when sending alerts.', max_length=32, null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text=b'Display name for the oncall schedule.', unique=True, max_length=50)),
                ('ical_url', models.TextField(help_text=b'ical url of the oncall schedule.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ScheduleProblems',
            fields=[
                ('schedule', models.OneToOneField(related_name='problems', primary_key=True, serialize=False, to='cabotapp.Schedule')),
                ('silence_warnings_until', models.DateTimeField(help_text=b'Silence configuration warning emails to the fallback officer (e.g. about gaps in the schedule) until this time. This will also display a warning in the schedules list.', null=True)),
                ('text', models.TextField(help_text=b'Description of the problems with this schedule.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.TextField()),
                ('alerts_enabled', models.BooleanField(default=True, help_text=b'Alert when this service is not healthy.')),
                ('last_alert_sent', models.DateTimeField(null=True, blank=True)),
                ('email_alert', models.BooleanField(default=False)),
                ('hipchat_alert', models.BooleanField(default=True)),
                ('sms_alert', models.BooleanField(default=False)),
                ('telephone_alert', models.BooleanField(default=False, help_text=b'Must be enabled, and check importance set to Critical, to receive telephone alerts.')),
                ('overall_status', models.TextField(default=b'PASSING')),
                ('old_overall_status', models.TextField(default=b'PASSING')),
                ('hackpad_id', models.TextField(help_text=b'Gist, Hackpad or Refheap js embed with recovery instructions e.g. https://you.hackpad.com/some_document.js', null=True, verbose_name=b'Recovery instructions', blank=True)),
                ('hipchat_room_id', models.PositiveIntegerField(help_text=b'Id of the Hipchat room to be alerted for this service (can be none).', null=True, blank=True)),
                ('mattermost_channel_id', models.CharField(help_text=b'ID of the Mattermost room to be alerted for this service (leave blank for default).', max_length=32, null=True, blank=True)),
                ('url', models.TextField(help_text=b'URL of service.', blank=True)),
                ('alerts', models.ManyToManyField(help_text=b'Alerts channels through which you wish to be notified', to='cabotapp.AlertPlugin', blank=True)),
                ('hipchat_instance', models.ForeignKey(blank=True, to='cabotapp.HipchatInstance', help_text=b'Hipchat instance to send Hipchat alerts to (can be none if Hipchat alerts disabled).', null=True)),
                ('mattermost_instance', models.ForeignKey(blank=True, to='cabotapp.MatterMostInstance', help_text=b'Mattermost instance to send alerts to (can be blank if Mattermost alerts are disabled).', null=True)),
                ('schedules', models.ManyToManyField(help_text=b'Oncall schedule to be alerted.', to='cabotapp.Schedule', null=True, blank=True)),
            ],
            options={
                'ordering': ['name'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ServiceStatusSnapshot',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(db_index=True)),
                ('num_checks_active', models.IntegerField(default=0)),
                ('num_checks_passing', models.IntegerField(default=0)),
                ('num_checks_failing', models.IntegerField(default=0)),
                ('overall_status', models.TextField(default=b'PASSING')),
                ('did_send_alert', models.IntegerField(default=False)),
                ('service', models.ForeignKey(related_name='snapshots', to='cabotapp.Service')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Shift',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('start', models.DateTimeField()),
                ('end', models.DateTimeField()),
                ('uid', models.TextField()),
                ('deleted', models.BooleanField(default=False)),
                ('schedule', models.ForeignKey(default=1, to='cabotapp.Schedule')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='StatusCheck',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.TextField()),
                ('active', models.BooleanField(default=True, help_text=b'If not active, check will not be used to calculate service status and will not trigger alerts.')),
                ('use_activity_counter', models.BooleanField(default=False, help_text=b"When enabled, a check's 'activity counter' is used to tell if the check can run. The activity counter starts at zero and may be incremented or decremented via API call. When incremented above zero, the check may run. When decremented to zero, the check will not run. This allows external processes to enable or disable a check as needed. (Note: the check must also be marked 'Active' to run.)")),
                ('importance', models.CharField(default=b'ERROR', help_text=b'Severity level of a failure. Critical alerts are for failures you want to wake you up at 2am, Errors are things you can sleep through but need to fix in the morning, and warnings for less important things.', max_length=30, choices=[(b'WARNING', b'Warning'), (b'ERROR', b'Error'), (b'CRITICAL', b'Critical')])),
                ('frequency', models.PositiveIntegerField(default=5, help_text=b'Minutes between each check.')),
                ('retries', models.PositiveIntegerField(default=0, help_text=b'Number of successive failures permitted before check will be marked as failed. Default is 0, i.e. fail on first failure.', null=True)),
                ('run_delay', models.PositiveIntegerField(default=0, help_text=b'Minutes to delay running the check, between 0-60. Only for checks using activity counters. A run delay can alleviate race conditions between an activity-counted check first running, and metrics being available.', validators=[django.core.validators.MaxValueValidator(60)])),
                ('calculated_status', models.CharField(default=b'passing', max_length=50, blank=True, choices=[(b'passing', b'passing'), (b'intermittent', b'intermittent'), (b'failing', b'failing')])),
                ('last_run', models.DateTimeField(null=True)),
                ('cached_health', models.TextField(null=True, editable=False)),
                ('runbook', models.TextField(default=None, help_text=b'Notes for on-calls to correctly diagnose and resolve the alert. Supports HTML!', null=True, blank=True)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='JenkinsStatusCheck',
            fields=[
                ('statuscheck_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cabotapp.StatusCheck')),
                ('max_queued_build_time', models.PositiveIntegerField(help_text=b'Alert if build queued for more than this many minutes.', null=True, blank=True)),
                ('max_build_failures', models.PositiveIntegerField(default=0, help_text=b'Alert if more than this many consecutive failures (default=0)')),
            ],
            options={
                'abstract': False,
            },
            bases=('cabotapp.statuscheck',),
        ),
        migrations.CreateModel(
            name='HttpStatusCheck',
            fields=[
                ('statuscheck_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cabotapp.StatusCheck')),
                ('endpoint', models.TextField(help_text=b'HTTP(S) endpoint to poll.', null=True)),
                ('username', models.TextField(help_text=b'Basic auth username.', null=True, blank=True)),
                ('password', models.TextField(help_text=b'Basic auth password.', null=True, blank=True)),
                ('http_method', models.CharField(default=b'GET', help_text=b'The method to use for invocation', max_length=10, choices=[(b'GET', b'GET'), (b'POST', b'POST'), (b'HEAD', b'HEAD')])),
                ('http_params', models.TextField(default=None, help_text=b'Yaml representation of "header: regex" to send as parameters', null=True, blank=True)),
                ('http_body', models.TextField(default=None, help_text=b'Yaml representation of key: value to send as data', null=True, blank=True)),
                ('allow_http_redirects', models.BooleanField(default=True, help_text=b'Indicates if the check should follow an http redirect')),
                ('text_match', models.TextField(help_text=b'Regex to match against source of page.', null=True, blank=True)),
                ('header_match', models.TextField(default=None, help_text=b'Yaml representation of "header: regex" to match in the results', null=True, blank=True)),
                ('timeout', cabot.cabotapp.fields.PositiveIntegerMaxField(default=30, help_text=b'Time out after this many seconds.', null=True, max_value=32)),
                ('verify_ssl_certificate', models.BooleanField(default=True, help_text=b'Set to false to allow not try to verify ssl certificates (default True)')),
                ('status_code', models.TextField(default=200, help_text=b'Status code expected from endpoint.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('cabotapp.statuscheck',),
        ),
        migrations.CreateModel(
            name='StatusCheckResult',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(db_index=True)),
                ('time_complete', models.DateTimeField(null=True, db_index=True)),
                ('raw_data', models.TextField(null=True)),
                ('succeeded', models.BooleanField(default=False)),
                ('error', models.TextField(null=True)),
                ('job_number', models.PositiveIntegerField(null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TCPStatusCheck',
            fields=[
                ('statuscheck_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='cabotapp.StatusCheck')),
                ('address', models.CharField(help_text=b'IP address or hostname to monitor', max_length=1024)),
                ('port', models.PositiveIntegerField(help_text=b'Port to connect to')),
                ('timeout', cabot.cabotapp.fields.PositiveIntegerMaxField(default=8, help_text=b'Time out on idle connection after this many seconds', max_value=16)),
            ],
            options={
                'abstract': False,
            },
            bases=('cabotapp.statuscheck',),
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('mobile_number', models.CharField(default=b'', max_length=20, blank=True)),
                ('hipchat_alias', models.CharField(default=b'', max_length=50, blank=True)),
                ('user', models.OneToOneField(related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='statuscheckresult',
            name='status_check',
            field=models.ForeignKey(to='cabotapp.StatusCheck'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='statuscheck',
            name='created_by',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='statuscheck',
            name='polymorphic_ctype',
            field=models.ForeignKey(related_name='polymorphic_cabotapp.statuscheck_set', editable=False, to='contenttypes.ContentType', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='service',
            name='status_checks',
            field=models.ManyToManyField(help_text=b'Checks used to calculate service status.', to='cabotapp.StatusCheck', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='service',
            name='users_to_notify',
            field=models.ManyToManyField(help_text=b'Users who should receive alerts.', to=settings.AUTH_USER_MODEL, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='schedule',
            name='fallback_officer',
            field=models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, help_text=b'Fallback officer to alert if the duty officer is unavailable.', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='alertpluginuserdata',
            name='user',
            field=models.ForeignKey(editable=False, to='cabotapp.UserProfile'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='alertpluginuserdata',
            unique_together=set([('title', 'user')]),
        ),
        migrations.AddField(
            model_name='activitycounter',
            name='status_check',
            field=models.OneToOneField(related_name='activity_counter', to='cabotapp.StatusCheck'),
            preserve_default=True,
        ),
    ]
