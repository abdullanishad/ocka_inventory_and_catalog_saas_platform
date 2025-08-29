from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="code",
            field=models.CharField(
                max_length=6,
                blank=True,
                default="",
                help_text="Short code used in SKU (auto if blank, e.g. PANT/SHRT).",
            ),
        ),
    ]
