import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0002_alert"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationPref",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("channel", models.CharField(
                    choices=[("telegram", "Telegram bot"), ("email", "Email")],
                    default="telegram",
                    max_length=16,
                )),
                ("telegram_chat_id", models.CharField(blank=True, max_length=32)),
                ("is_active", models.BooleanField(default=True)),
                ("min_severity", models.CharField(
                    choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Critical")],
                    default="warning",
                    max_length=16,
                )),
                ("enabled_metrics", models.JSONField(
                    blank=True,
                    default=list,
                    help_text="Empty list = all metrics enabled",
                )),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="notification_pref",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "Notification preference",
                "verbose_name_plural": "Notification preferences",
            },
        ),
    ]
