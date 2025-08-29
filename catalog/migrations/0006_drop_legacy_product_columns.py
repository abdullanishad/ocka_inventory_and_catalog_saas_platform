from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_create_categorysize"),  # adjust to your last migration
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE catalog_product DROP COLUMN IF EXISTS current_stock;
                ALTER TABLE catalog_product DROP COLUMN IF EXISTS fit_type_id;
            """,
            reverse_sql="""
                ALTER TABLE catalog_product ADD COLUMN current_stock integer NOT NULL DEFAULT 0;
                ALTER TABLE catalog_product ADD COLUMN fit_type_id bigint NULL;
            """,
        ),
    ]
