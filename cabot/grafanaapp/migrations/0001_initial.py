# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'GrafanaInstance'
        db.create_table(u'grafanaapp_grafanainstance', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=30)),
            ('url', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('api_token', self.gf('django.db.models.fields.CharField')(max_length=100)),
        ))
        db.send_create_signal('grafanaapp', ['GrafanaInstance'])

        # Adding model 'GrafanaDataSource'
        db.create_table(u'grafanaapp_grafanadatasource', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('grafana_source_name', self.gf('django.db.models.fields.CharField')(max_length=30)),
            ('grafana_instance', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['grafanaapp.GrafanaInstance'])),
            ('metrics_source_base', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['metricsapp.MetricsSourceBase'])),
        ))
        db.send_create_signal('grafanaapp', ['GrafanaDataSource'])


    def backwards(self, orm):
        # Deleting model 'GrafanaInstance'
        db.delete_table(u'grafanaapp_grafanainstance')

        # Deleting model 'GrafanaDataSource'
        db.delete_table(u'grafanaapp_grafanadatasource')


    models = {
        'grafanaapp.grafanadatasource': {
            'Meta': {'object_name': 'GrafanaDataSource'},
            'grafana_instance': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['grafanaapp.GrafanaInstance']"}),
            'grafana_source_name': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'metrics_source_base': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['metricsapp.MetricsSourceBase']"})
        },
        'grafanaapp.grafanainstance': {
            'Meta': {'object_name': 'GrafanaInstance'},
            'api_token': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'}),
            'sources': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['metricsapp.MetricsSourceBase']", 'through': "orm['grafanaapp.GrafanaDataSource']", 'symmetrical': 'False'}),
            'url': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'metricsapp.metricssourcebase': {
            'Meta': {'object_name': 'MetricsSourceBase'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        }
    }

    complete_apps = ['grafanaapp']