# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cabotapp', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='alertplugin',
            name='polymorphic_ctype',
            field=models.ForeignKey(related_name='polymorphic_cabotapp.alertplugin_set+', editable=False, to='contenttypes.ContentType', null=True),
        ),
        migrations.AlterField(
            model_name='alertpluginuserdata',
            name='polymorphic_ctype',
            field=models.ForeignKey(related_name='polymorphic_cabotapp.alertpluginuserdata_set+', editable=False, to='contenttypes.ContentType', null=True),
        ),
        migrations.AlterField(
            model_name='service',
            name='schedules',
            field=models.ManyToManyField(help_text=b'Oncall schedule to be alerted.', to='cabotapp.Schedule', blank=True),
        ),
        migrations.AlterField(
            model_name='statuscheck',
            name='polymorphic_ctype',
            field=models.ForeignKey(related_name='polymorphic_cabotapp.statuscheck_set+', editable=False, to='contenttypes.ContentType', null=True),
        ),
    ]
