from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_create_categorysize"),  # adjust if latest migration differs
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE catalog_product DROP COLUMN IF EXISTS minimum_order_qty;",
            reverse_sql="ALTER TABLE catalog_product ADD COLUMN minimum_order_qty integer DEFAULT 1;",
        ),
    ]
