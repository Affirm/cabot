# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'GraphiteStatusCheck'
        db.create_table(u'cabotapp_graphitestatuscheck', (
            (u'statuscheck_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cabotapp.StatusCheck'], unique=True, primary_key=True)),
            ('metric', self.gf('django.db.models.fields.TextField')(null=True)),
            ('metric_selector', self.gf('django.db.models.fields.CharField')(default='value', max_length=50)),
            ('group_by', self.gf('django.db.models.fields.CharField')(default='', max_length=50)),
            ('fill_empty', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True)),
            ('where_clause', self.gf('django.db.models.fields.CharField')(default='', max_length=256, blank=True)),
            ('check_type', self.gf('django.db.models.fields.CharField')(max_length=100, null=True)),
            ('value', self.gf('django.db.models.fields.TextField')(null=True)),
            ('expected_num_hosts', self.gf('django.db.models.fields.IntegerField')(default=0, null=True)),
            ('expected_num_metrics', self.gf('django.db.models.fields.IntegerField')(default=0, null=True)),
        ))
        db.send_create_signal(u'cabotapp', ['GraphiteStatusCheck'])

        # Adding model 'HttpStatusCheck'
        db.create_table(u'cabotapp_httpstatuscheck', (
            (u'statuscheck_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cabotapp.StatusCheck'], unique=True, primary_key=True)),
            ('endpoint', self.gf('django.db.models.fields.TextField')(null=True)),
            ('username', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('password', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('http_method', self.gf('django.db.models.fields.CharField')(default='GET', max_length=10)),
            ('http_params', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True)),
            ('http_body', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True)),
            ('allow_http_redirects', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('text_match', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('header_match', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True)),
            ('status_code', self.gf('django.db.models.fields.TextField')(default=200, null=True)),
            ('timeout', self.gf('django.db.models.fields.IntegerField')(default=30, null=True)),
            ('verify_ssl_certificate', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal(u'cabotapp', ['HttpStatusCheck'])

        # Adding model 'InfluxDBStatusCheck'
        db.create_table(u'cabotapp_influxdbstatuscheck', (
            (u'graphitestatuscheck_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cabotapp.GraphiteStatusCheck'], unique=True, primary_key=True)),
        ))
        db.send_create_signal(u'cabotapp', ['InfluxDBStatusCheck'])

        # Adding model 'ICMPStatusCheck'
        db.create_table(u'cabotapp_icmpstatuscheck', (
            (u'statuscheck_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cabotapp.StatusCheck'], unique=True, primary_key=True)),
        ))
        db.send_create_signal(u'cabotapp', ['ICMPStatusCheck'])

        # Adding model 'JenkinsStatusCheck'
        db.create_table(u'cabotapp_jenkinsstatuscheck', (
            (u'statuscheck_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cabotapp.StatusCheck'], unique=True, primary_key=True)),
            ('max_queued_build_time', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'cabotapp', ['JenkinsStatusCheck'])

        # Deleting field 'StatusCheck.fill_empty'
        db.delete_column(u'cabotapp_statuscheck', 'fill_empty')

        # Deleting field 'StatusCheck.username'
        db.delete_column(u'cabotapp_statuscheck', 'username')

        # Deleting field 'StatusCheck.check_type'
        db.delete_column(u'cabotapp_statuscheck', 'check_type')

        # Deleting field 'StatusCheck.http_body'
        db.delete_column(u'cabotapp_statuscheck', 'http_body')

        # Deleting field 'StatusCheck.where_clause'
        db.delete_column(u'cabotapp_statuscheck', 'where_clause')

        # Deleting field 'StatusCheck.allow_http_redirects'
        db.delete_column(u'cabotapp_statuscheck', 'allow_http_redirects')

        # Deleting field 'StatusCheck.status_code'
        db.delete_column(u'cabotapp_statuscheck', 'status_code')

        # Deleting field 'StatusCheck.metric'
        db.delete_column(u'cabotapp_statuscheck', 'metric')

        # Deleting field 'StatusCheck.max_queued_build_time'
        db.delete_column(u'cabotapp_statuscheck', 'max_queued_build_time')

        # Deleting field 'StatusCheck.header_match'
        db.delete_column(u'cabotapp_statuscheck', 'header_match')

        # Deleting field 'StatusCheck.http_params'
        db.delete_column(u'cabotapp_statuscheck', 'http_params')

        # Deleting field 'StatusCheck.password'
        db.delete_column(u'cabotapp_statuscheck', 'password')

        # Deleting field 'StatusCheck.expected_num_hosts'
        db.delete_column(u'cabotapp_statuscheck', 'expected_num_hosts')

        # Deleting field 'StatusCheck.value'
        db.delete_column(u'cabotapp_statuscheck', 'value')

        # Deleting field 'StatusCheck.endpoint'
        db.delete_column(u'cabotapp_statuscheck', 'endpoint')

        # Deleting field 'StatusCheck.verify_ssl_certificate'
        db.delete_column(u'cabotapp_statuscheck', 'verify_ssl_certificate')

        # Deleting field 'StatusCheck.metric_selector'
        db.delete_column(u'cabotapp_statuscheck', 'metric_selector')

        # Deleting field 'StatusCheck.group_by'
        db.delete_column(u'cabotapp_statuscheck', 'group_by')

        # Deleting field 'StatusCheck.http_method'
        db.delete_column(u'cabotapp_statuscheck', 'http_method')

        # Deleting field 'StatusCheck.timeout'
        db.delete_column(u'cabotapp_statuscheck', 'timeout')

        # Deleting field 'StatusCheck.text_match'
        db.delete_column(u'cabotapp_statuscheck', 'text_match')

        # Deleting field 'StatusCheck.expected_num_metrics'
        db.delete_column(u'cabotapp_statuscheck', 'expected_num_metrics')


    def backwards(self, orm):
        # Deleting model 'GraphiteStatusCheck'
        db.delete_table(u'cabotapp_graphitestatuscheck')

        # Deleting model 'HttpStatusCheck'
        db.delete_table(u'cabotapp_httpstatuscheck')

        # Deleting model 'InfluxDBStatusCheck'
        db.delete_table(u'cabotapp_influxdbstatuscheck')

        # Deleting model 'ICMPStatusCheck'
        db.delete_table(u'cabotapp_icmpstatuscheck')

        # Deleting model 'JenkinsStatusCheck'
        db.delete_table(u'cabotapp_jenkinsstatuscheck')

        # Adding field 'StatusCheck.fill_empty'
        db.add_column(u'cabotapp_statuscheck', 'fill_empty',
                      self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True),
                      keep_default=False)

        # Adding field 'StatusCheck.username'
        db.add_column(u'cabotapp_statuscheck', 'username',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Adding field 'StatusCheck.check_type'
        db.add_column(u'cabotapp_statuscheck', 'check_type',
                      self.gf('django.db.models.fields.CharField')(max_length=100, null=True),
                      keep_default=False)

        # Adding field 'StatusCheck.http_body'
        db.add_column(u'cabotapp_statuscheck', 'http_body',
                      self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True),
                      keep_default=False)

        # Adding field 'StatusCheck.where_clause'
        db.add_column(u'cabotapp_statuscheck', 'where_clause',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=256, blank=True),
                      keep_default=False)

        # Adding field 'StatusCheck.allow_http_redirects'
        db.add_column(u'cabotapp_statuscheck', 'allow_http_redirects',
                      self.gf('django.db.models.fields.BooleanField')(default=True),
                      keep_default=False)

        # Adding field 'StatusCheck.status_code'
        db.add_column(u'cabotapp_statuscheck', 'status_code',
                      self.gf('django.db.models.fields.TextField')(default=200, null=True),
                      keep_default=False)

        # Adding field 'StatusCheck.metric'
        db.add_column(u'cabotapp_statuscheck', 'metric',
                      self.gf('django.db.models.fields.TextField')(null=True),
                      keep_default=False)

        # Adding field 'StatusCheck.max_queued_build_time'
        db.add_column(u'cabotapp_statuscheck', 'max_queued_build_time',
                      self.gf('django.db.models.fields.IntegerField')(null=True, blank=True),
                      keep_default=False)

        # Adding field 'StatusCheck.header_match'
        db.add_column(u'cabotapp_statuscheck', 'header_match',
                      self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True),
                      keep_default=False)

        # Adding field 'StatusCheck.http_params'
        db.add_column(u'cabotapp_statuscheck', 'http_params',
                      self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True),
                      keep_default=False)

        # Adding field 'StatusCheck.password'
        db.add_column(u'cabotapp_statuscheck', 'password',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Adding field 'StatusCheck.expected_num_hosts'
        db.add_column(u'cabotapp_statuscheck', 'expected_num_hosts',
                      self.gf('django.db.models.fields.IntegerField')(default=0, null=True),
                      keep_default=False)

        # Adding field 'StatusCheck.value'
        db.add_column(u'cabotapp_statuscheck', 'value',
                      self.gf('django.db.models.fields.TextField')(null=True),
                      keep_default=False)

        # Adding field 'StatusCheck.endpoint'
        db.add_column(u'cabotapp_statuscheck', 'endpoint',
                      self.gf('django.db.models.fields.TextField')(null=True),
                      keep_default=False)

        # Adding field 'StatusCheck.verify_ssl_certificate'
        db.add_column(u'cabotapp_statuscheck', 'verify_ssl_certificate',
                      self.gf('django.db.models.fields.BooleanField')(default=True),
                      keep_default=False)

        # Adding field 'StatusCheck.metric_selector'
        db.add_column(u'cabotapp_statuscheck', 'metric_selector',
                      self.gf('django.db.models.fields.CharField')(default='value', max_length=50),
                      keep_default=False)

        # Adding field 'StatusCheck.group_by'
        db.add_column(u'cabotapp_statuscheck', 'group_by',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=50),
                      keep_default=False)

        # Adding field 'StatusCheck.http_method'
        db.add_column(u'cabotapp_statuscheck', 'http_method',
                      self.gf('django.db.models.fields.CharField')(default='GET', max_length=10),
                      keep_default=False)

        # Adding field 'StatusCheck.timeout'
        db.add_column(u'cabotapp_statuscheck', 'timeout',
                      self.gf('django.db.models.fields.IntegerField')(default=30, null=True),
                      keep_default=False)

        # Adding field 'StatusCheck.text_match'
        db.add_column(u'cabotapp_statuscheck', 'text_match',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Adding field 'StatusCheck.expected_num_metrics'
        db.add_column(u'cabotapp_statuscheck', 'expected_num_metrics',
                      self.gf('django.db.models.fields.IntegerField')(default=0, null=True),
                      keep_default=False)


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'cabotapp.alertplugin': {
            'Meta': {'object_name': 'AlertPlugin'},
            'enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'polymorphic_ctype': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'polymorphic_cabotapp.alertplugin_set'", 'null': 'True', 'to': u"orm['contenttypes.ContentType']"}),
            'title': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'cabotapp.alertpluginuserdata': {
            'Meta': {'unique_together': "(('title', 'user'),)", 'object_name': 'AlertPluginUserData'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'polymorphic_ctype': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'polymorphic_cabotapp.alertpluginuserdata_set'", 'null': 'True', 'to': u"orm['contenttypes.ContentType']"}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['cabotapp.UserProfile']"})
        },
        u'cabotapp.graphitestatuscheck': {
            'Meta': {'ordering': "['name']", 'object_name': 'GraphiteStatusCheck', '_ormbases': [u'cabotapp.StatusCheck']},
            'check_type': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True'}),
            'expected_num_hosts': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'expected_num_metrics': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'fill_empty': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'group_by': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '50'}),
            'metric': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'metric_selector': ('django.db.models.fields.CharField', [], {'default': "'value'", 'max_length': '50'}),
            u'statuscheck_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cabotapp.StatusCheck']", 'unique': 'True', 'primary_key': 'True'}),
            'value': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'where_clause': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '256', 'blank': 'True'})
        },
        u'cabotapp.httpstatuscheck': {
            'Meta': {'ordering': "['name']", 'object_name': 'HttpStatusCheck', '_ormbases': [u'cabotapp.StatusCheck']},
            'allow_http_redirects': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'endpoint': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'header_match': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'http_body': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'http_method': ('django.db.models.fields.CharField', [], {'default': "'GET'", 'max_length': '10'}),
            'http_params': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'password': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'status_code': ('django.db.models.fields.TextField', [], {'default': '200', 'null': 'True'}),
            u'statuscheck_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cabotapp.StatusCheck']", 'unique': 'True', 'primary_key': 'True'}),
            'text_match': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'timeout': ('django.db.models.fields.IntegerField', [], {'default': '30', 'null': 'True'}),
            'username': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'verify_ssl_certificate': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'cabotapp.icmpstatuscheck': {
            'Meta': {'ordering': "['name']", 'object_name': 'ICMPStatusCheck', '_ormbases': [u'cabotapp.StatusCheck']},
            u'statuscheck_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cabotapp.StatusCheck']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cabotapp.influxdbstatuscheck': {
            'Meta': {'ordering': "['name']", 'object_name': 'InfluxDBStatusCheck', '_ormbases': [u'cabotapp.GraphiteStatusCheck']},
            u'graphitestatuscheck_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cabotapp.GraphiteStatusCheck']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cabotapp.instance': {
            'Meta': {'ordering': "['name']", 'object_name': 'Instance'},
            'address': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'alerts': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['cabotapp.AlertPlugin']", 'symmetrical': 'False', 'blank': 'True'}),
            'alerts_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'email_alert': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'hackpad_id': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'hipchat_alert': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_alert_sent': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {}),
            'old_overall_status': ('django.db.models.fields.TextField', [], {'default': "'PASSING'"}),
            'overall_status': ('django.db.models.fields.TextField', [], {'default': "'PASSING'"}),
            'schedules': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['cabotapp.Schedule']", 'null': 'True', 'blank': 'True'}),
            'sms_alert': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'status_checks': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['cabotapp.StatusCheck']", 'symmetrical': 'False', 'blank': 'True'}),
            'telephone_alert': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'users_to_notify': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.User']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'cabotapp.instancestatussnapshot': {
            'Meta': {'object_name': 'InstanceStatusSnapshot'},
            'did_send_alert': ('django.db.models.fields.IntegerField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'snapshots'", 'to': u"orm['cabotapp.Instance']"}),
            'num_checks_active': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_checks_failing': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_checks_passing': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'overall_status': ('django.db.models.fields.TextField', [], {'default': "'PASSING'"}),
            'time': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'})
        },
        u'cabotapp.jenkinsstatuscheck': {
            'Meta': {'ordering': "['name']", 'object_name': 'JenkinsStatusCheck', '_ormbases': [u'cabotapp.StatusCheck']},
            'max_queued_build_time': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            u'statuscheck_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['cabotapp.StatusCheck']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'cabotapp.schedule': {
            'Meta': {'object_name': 'Schedule'},
            'fallback_officer': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'ical_url': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50'})
        },
        u'cabotapp.service': {
            'Meta': {'ordering': "['name']", 'object_name': 'Service'},
            'alerts': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['cabotapp.AlertPlugin']", 'symmetrical': 'False', 'blank': 'True'}),
            'alerts_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'email_alert': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'hackpad_id': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'hipchat_alert': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instances': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['cabotapp.Instance']", 'symmetrical': 'False', 'blank': 'True'}),
            'last_alert_sent': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {}),
            'old_overall_status': ('django.db.models.fields.TextField', [], {'default': "'PASSING'"}),
            'overall_status': ('django.db.models.fields.TextField', [], {'default': "'PASSING'"}),
            'schedules': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['cabotapp.Schedule']", 'null': 'True', 'blank': 'True'}),
            'sms_alert': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'status_checks': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['cabotapp.StatusCheck']", 'symmetrical': 'False', 'blank': 'True'}),
            'telephone_alert': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'url': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'users_to_notify': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.User']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'cabotapp.servicestatussnapshot': {
            'Meta': {'object_name': 'ServiceStatusSnapshot'},
            'did_send_alert': ('django.db.models.fields.IntegerField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'num_checks_active': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_checks_failing': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_checks_passing': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'overall_status': ('django.db.models.fields.TextField', [], {'default': "'PASSING'"}),
            'service': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'snapshots'", 'to': u"orm['cabotapp.Service']"}),
            'time': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'})
        },
        u'cabotapp.shift': {
            'Meta': {'object_name': 'Shift'},
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'end': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'schedule': ('django.db.models.fields.related.ForeignKey', [], {'default': '1', 'to': u"orm['cabotapp.Schedule']"}),
            'start': ('django.db.models.fields.DateTimeField', [], {}),
            'uid': ('django.db.models.fields.TextField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"})
        },
        u'cabotapp.statuscheck': {
            'Meta': {'ordering': "['name']", 'object_name': 'StatusCheck'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cached_health': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'calculated_status': ('django.db.models.fields.CharField', [], {'default': "'passing'", 'max_length': '50', 'blank': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']", 'null': 'True'}),
            'debounce': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'frequency': ('django.db.models.fields.IntegerField', [], {'default': '5'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'importance': ('django.db.models.fields.CharField', [], {'default': "'ERROR'", 'max_length': '30'}),
            'interval': ('django.db.models.fields.IntegerField', [], {'default': '5'}),
            'last_run': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {}),
            'polymorphic_ctype': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'polymorphic_cabotapp.statuscheck_set'", 'null': 'True', 'to': u"orm['contenttypes.ContentType']"})
        },
        u'cabotapp.statuscheckresult': {
            'Meta': {'object_name': 'StatusCheckResult'},
            'check': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['cabotapp.StatusCheck']"}),
            'error': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'job_number': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'raw_data': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'succeeded': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'time_complete': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'db_index': 'True'})
        },
        u'cabotapp.userprofile': {
            'Meta': {'object_name': 'UserProfile'},
            'hipchat_alias': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '50', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mobile_number': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '20', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'profile'", 'unique': 'True', 'to': u"orm['auth.User']"})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        }
    }

    complete_apps = ['cabotapp']