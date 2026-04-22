import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0001_initial"),
        ("social",    "0002_publicsharelink"),
    ]

    operations = [
        migrations.CreateModel(
            name="Alert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("metric", models.CharField(
                    choices=[
                        ("engagement_rate", "Engagement rate"),
                        ("follower_growth", "Follower growth"),
                        ("sentiment_ratio", "Sentiment ratio (positive %)"),
                        ("posts_per_day",   "Posts per day"),
                        ("comment_volume",  "Comment volume"),
                    ],
                    db_index=True,
                    max_length=32,
                )),
                ("direction", models.CharField(
                    choices=[("spike", "Spike (up)"), ("drop", "Drop (down)")],
                    max_length=8,
                )),
                ("severity", models.CharField(
                    choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Critical")],
                    db_index=True,
                    default="warning",
                    max_length=16,
                )),
                ("value",       models.FloatField(help_text="Observed value on the detection day")),
                ("baseline",    models.FloatField(help_text="Rolling mean over the look-back window")),
                ("z_score",     models.FloatField(help_text="Signed z-score (negative = drop)")),
                ("window_days", models.PositiveSmallIntegerField(default=14)),
                ("message",     models.CharField(blank=True, max_length=255)),
                ("is_read",     models.BooleanField(db_index=True, default=False)),
                ("is_resolved", models.BooleanField(db_index=True, default=False)),
                ("detected_for", models.DateField(db_index=True, help_text="Calendar day the anomaly refers to")),
                ("account", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="alerts",
                    to="social.connectedaccount",
                )),
            ],
            options={
                "ordering": ["-detected_for", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["account", "-detected_for"], name="analytics_a_account_d0b5f3_idx"),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["severity", "is_resolved"], name="analytics_a_severit_7a2e1c_idx"),
        ),
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.UniqueConstraint(
                fields=("account", "metric", "detected_for"),
                name="uniq_alert_per_account_metric_day",
            ),
        ),
    ]
