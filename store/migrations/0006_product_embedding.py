# Adds the image-search fingerprint to Product.
# Only this field is added here. Other model/migration drift that existed
# before this change is intentionally left alone.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0005_order_orderitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="embedding",
            field=models.JSONField(blank=True, editable=False, null=True),
        ),
    ]
