

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('career', '0003_remove_academicrecord_is_11th_only'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('registration', 'Registration / Login'), ('marks', 'Marks Entry'), ('test', 'Personality Test'), ('results', 'Results / Recommendations'), ('general', 'General')], default='general', max_length=20)),
                ('rating', models.PositiveSmallIntegerField(default=5)),
                ('message', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='feedbacks', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
