"""
Load products from a CSV file. The photos are read from media/products/,
the same folder the website serves them from, so there is only one copy.

    python manage.py import_catalog                       # data/catalog.csv + media/products/
    python manage.py import_catalog --csv my.csv --images other_folder   # copies photos from there
    python manage.py import_catalog --dry-run             # check everything, change nothing

CSV columns: id,name,price,stock,is_active,category,image

- Safe to run again: a product is found by its slug (name + CSV id) and updated, never duplicated.
- Products already in the shop (not from this CSV) are not touched.
- A row whose photo file is missing is skipped and listed at the end.
- The CSV "id" is only used to make the slug unique. The database assigns its own ids.
- After importing, run:  python manage.py build_embeddings   (so photo search sees the new products)
"""

import csv
import shutil
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from store.models import Category, Product

# CSV category name -> (shop category name, slug). Names not listed here become new categories.
CATEGORY_MAP = {
    "pokémon card": ("Pokemon Cards", "pokemon-cards"),
    "pokemon card": ("Pokemon Cards", "pokemon-cards"),
    "lego": ("Lego", "lego"),
    "gunpla": ("Gundam", "gundam"),
}

REQUIRED = ["id", "name", "price", "stock", "is_active", "category", "image"]


def get_category(name, cache):
    key = name.strip().lower()
    if key in cache:
        return cache[key]
    shop_name, slug = CATEGORY_MAP.get(key, (name.strip(), slugify(name) or "other"))
    category, _ = Category.objects.get_or_create(slug=slug, defaults={"name": shop_name})
    cache[key] = category
    return category


def make_slug(name, csv_id):
    return f"{slugify(name)[:40].strip('-') or 'product'}-{csv_id}"  # SlugField max is 50


class Command(BaseCommand):
    help = "Import products and photos from a CSV file."

    def add_arguments(self, parser):
        base = settings.BASE_DIR
        parser.add_argument("--csv", default=str(base / "data" / "catalog.csv"))
        parser.add_argument("--images", default=str(Path(settings.MEDIA_ROOT) / "products"))
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        csv_path, images_dir = Path(options["csv"]), Path(options["images"])
        dry = options["dry_run"]
        if not csv_path.exists():
            raise CommandError(f"CSV not found: {csv_path}")

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            missing_cols = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
            if missing_cols:
                raise CommandError(f"CSV is missing columns: {', '.join(missing_cols)}")
            rows = list(reader)

        media_dir = Path(settings.MEDIA_ROOT) / "products"
        categories, created, updated = {}, 0, 0
        no_photo, bad_rows = [], []

        for line, row in enumerate(rows, start=2):
            try:
                name = row["name"].strip()
                price = Decimal(row["price"].strip())
                stock = int(row["stock"])
                if not name or price < 0 or stock < 0:
                    raise ValueError("empty name, or negative price/stock")
                is_active = row["is_active"].strip().lower() in ("true", "1", "yes")
                image_name = Path(row["image"].strip()).name
                csv_id = int(row["id"])
            except (ValueError, InvalidOperation, KeyError) as error:
                bad_rows.append(f"line {line}: {error}")
                continue

            source = images_dir / image_name
            if not image_name or not source.is_file():
                no_photo.append(image_name or f"(line {line})")
                continue

            if dry:
                continue

            # Photos already in media/products/ stay where they are. Only a different
            # --images folder gets copied in.
            target = media_dir / image_name
            if not target.exists():
                media_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)

            product, was_created = Product.objects.get_or_create(
                slug=make_slug(name, csv_id),
                defaults={
                    "category": get_category(row["category"], categories),
                    "name": name,
                    "description": f"{name} ({row['category'].strip()})",
                    "price": price, "stock": stock, "is_active": is_active,
                    "image": f"products/{image_name}",
                },
            )
            if was_created:
                created += 1
                continue

            new_image = f"products/{image_name}"
            if product.image.name != new_image:
                product.embedding = None  # the photo changed, so the old fingerprint is wrong
            product.category = get_category(row["category"], categories)
            product.name, product.price, product.stock = name, price, stock
            product.is_active, product.image = is_active, new_image
            product.save()
            updated += 1

        ok_rows = len(rows) - len(no_photo) - len(bad_rows)
        if dry:
            self.stdout.write(f"Dry run: {ok_rows} of {len(rows)} rows are ready to import.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Created {created}, updated {updated}."))
            if ok_rows:
                self.stdout.write("Next: python manage.py build_embeddings")
        if no_photo:
            shown = ", ".join(no_photo[:10]) + (" ..." if len(no_photo) > 10 else "")
            self.stdout.write(self.style.WARNING(
                f"{len(no_photo)} row(s) skipped, photo not found in {images_dir}: {shown}"))
        for message in bad_rows[:10]:
            self.stdout.write(self.style.WARNING(f"Skipped bad row, {message}"))
        if len(bad_rows) > 10:
            self.stdout.write(self.style.WARNING(f"... and {len(bad_rows) - 10} more bad rows."))
