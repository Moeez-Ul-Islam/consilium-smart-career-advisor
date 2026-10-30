

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('career', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='academicrecord',
            name='board',
            field=models.CharField(blank=True, default='', help_text='Examination board key (see career/boards.py).', max_length=30),
        ),
    ]
