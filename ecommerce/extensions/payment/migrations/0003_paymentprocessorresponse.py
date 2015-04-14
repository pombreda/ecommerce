# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('basket', '0004_auto_20141007_2032'),
        ('payment', '0002_auto_20141007_2032'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentProcessorResponse',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('processor_name', models.CharField(max_length=255)),
                ('transaction_id', models.CharField(max_length=255)),
                ('response', jsonfield.fields.JSONField()),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('basket', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, verbose_name='Basket', blank=True, to='basket.Basket', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
