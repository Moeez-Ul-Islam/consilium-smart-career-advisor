

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('career', '0002_academicrecord_board'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='academicrecord',
            name='is_11th_only',
        ),
    ]
