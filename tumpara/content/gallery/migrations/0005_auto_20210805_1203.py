# Generated by Django 3.2.6 on 2021-08-05 12:03

from django.db import migrations, models
import django.db.models.manager


class Migration(migrations.Migration):

    dependencies = [
        ('gallery', '0004_auto_20210710_0932'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='autodevelopedphoto',
            options={'default_manager_name': 'active_objects', 'verbose_name': 'automatically developed photo', 'verbose_name_plural': 'automatically developed photos'},
        ),
        migrations.AlterModelOptions(
            name='rawphoto',
            options={'default_manager_name': 'active_objects', 'verbose_name': 'raw photo', 'verbose_name_plural': 'raw photos'},
        ),
        migrations.AlterModelManagers(
            name='autodevelopedphoto',
            managers=[
                ('active_objects', django.db.models.manager.Manager()),
            ],
        ),
        migrations.AlterModelManagers(
            name='rawphoto',
            managers=[
                ('active_objects', django.db.models.manager.Manager()),
            ],
        ),
        migrations.AddConstraint(
            model_name='autodevelopedphoto',
            constraint=models.UniqueConstraint(fields=('raw_source',), name='source_unique_for_autodeveloped_photos'),
        ),
    ]
