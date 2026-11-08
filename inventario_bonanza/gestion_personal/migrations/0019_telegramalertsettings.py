from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('gestion_personal', '0018_seed_initial_dining_halls')]

    operations = [
        migrations.CreateModel(
            name='TelegramAlertSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bot_token', models.CharField(blank=True, max_length=256)),
                ('common_chat_ids', models.TextField(blank=True)),
                ('server_chat_ids', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
