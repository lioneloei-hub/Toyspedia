"""
Run once after adding products (and whenever a product photo changes):

    python manage.py build_embeddings          # only products with no embedding yet
    python manage.py build_embeddings --force  # redo every product

The first run downloads the DINOv2 model (about 90 MB) from Hugging Face.
"""

from django.core.management.base import BaseCommand

from store import image_search
from store.models import Product


class Command(BaseCommand):
    help = "Compute DINOv2 image embeddings for product photos (used by image search)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recompute the embedding even for products that already have one.",
        )

    def handle(self, *args, **options):
        products = Product.objects.exclude(image="").order_by("id")
        if not options["force"]:
            products = products.filter(embedding__isnull=True)

        total = products.count()
        if total == 0:
            self.stdout.write("Nothing to do: every product already has an embedding.")
            return

        self.stdout.write(f"Embedding {total} product photo(s)...")
        done, failed = 0, 0
        for product in products:
            try:
                product.embedding = image_search.embed_image(product.image.path)
                product.save(update_fields=["embedding"])
                done += 1
                self.stdout.write(f"  ok    {product.slug}")
            except Exception as error:  # keep going; report the bad photo at the end
                failed += 1
                self.stdout.write(self.style.WARNING(f"  FAIL  {product.slug}: {error}"))

        self.stdout.write(self.style.SUCCESS(f"Saved {done} embedding(s)."))
        if failed:
            self.stdout.write(self.style.WARNING(f"{failed} product(s) failed. Fix the photo and run again."))
