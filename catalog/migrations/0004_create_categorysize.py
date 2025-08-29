from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0003_add_batch_ref_to_sizestock"),  # adjust if your last migration number differs
    ]

    operations = [
        migrations.CreateModel(
            name="CategorySize",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "category",
                    models.ForeignKey(on_delete=models.CASCADE, related_name="category_sizes", to="catalog.category"),
                ),
                (
                    "size",
                    models.ForeignKey(on_delete=models.PROTECT, to="catalog.size"),
                ),
            ],
            options={
                "ordering": ["order", "size__order", "size__name"],
                "unique_together": {("category", "size")},
            },
        ),
    ]
