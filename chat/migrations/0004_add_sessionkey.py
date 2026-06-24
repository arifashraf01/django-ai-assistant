from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0003_alter_document_options_chatmessage_document_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatmessage",
            name="session_key",
            field=models.CharField(max_length=100, null=True, blank=True, db_index=True),
        ),
    ]
