from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_add_code_to_category"),  # adjust if your last migration is different
    ]

    operations = [
        migrations.AddField(
            model_name="sizestock",
            name="batch_ref",
            field=models.CharField(
                max_length=40,
                blank=True,
                help_text="Optional batch/lot reference",
                default="",  # required so existing rows get a value
            ),
            preserve_default=False,
        ),
    ]
