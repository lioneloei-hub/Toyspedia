"""
image_search.py - reverse image search: a photo in, the most similar products out.

How it works:
  1. Every product photo was turned into 384 numbers by DINOv2 once, by
     `python manage.py build_embeddings`. Those numbers live on the Product row.
  2. When a visitor uploads a photo, we embed ONLY that photo.
  3. We compare it with every saved vector (cosine similarity = dot product
     of unit-length vectors) and return the best matches.

The saved vectors are loaded from the database once and kept in memory.
Saving or deleting a product clears that cache (see signals.py), so the
next search reloads it.
"""

import threading

import numpy as np

from .formatting import format_idr
from .models import Product

EMBEDDING_SIZE = 384  # dinov2-small hidden size

_lock = threading.Lock()
_index = None  # (matrix of unit vectors, product ids in the same row order)


class IndexNotReady(Exception):
    """No product has an embedding yet."""


def embed_image(image_source):
    """Return the DINOv2 vector for a file path or an open PIL image."""
    # Imported here, not at the top, because torch is large and slow to load.
    # Code that never searches (admin pages, most tests) never pays that cost.
    from .dinov2_embedding import compute_embedding
    return compute_embedding(image_source)


def _load_index():
    global _index
    with _lock:
        if _index is None:
            rows = list(
                Product.objects.filter(is_active=True, embedding__isnull=False)
                .order_by("id")
                .values_list("id", "embedding")
            )
            ids = [pk for pk, _ in rows]
            if rows:
                matrix = np.asarray([vec for _, vec in rows], dtype=np.float32)
                norms = np.linalg.norm(matrix, axis=1, keepdims=True)
                matrix = matrix / np.clip(norms, 1e-12, None)
            else:
                matrix = np.empty((0, EMBEDDING_SIZE), dtype=np.float32)
            _index = (matrix, ids)
        return _index


def reset_index():
    """Forget the in-memory vectors. The next search reloads them from the database."""
    global _index
    with _lock:
        _index = None


def search(image_source, top_n=3):
    """
    image_source: a file path or an open PIL image (the upload).
    Returns up to top_n dicts, most similar first.
    Raises IndexNotReady if build_embeddings has never been run.
    """
    matrix, ids = _load_index()
    if not ids:
        raise IndexNotReady()

    query = np.asarray(embed_image(image_source), dtype=np.float32)
    query = query / (np.linalg.norm(query) or 1.0)

    scores = matrix @ query  # one similarity per product
    best_rows = np.argsort(-scores)[:top_n]

    # Read name, price and stock fresh from the database, not from the cache,
    # so a sale or price change shows up at once.
    products = Product.objects.in_bulk([ids[i] for i in best_rows])

    results = []
    for row in best_rows:
        product = products.get(ids[row])
        if product is None:
            continue
        results.append({
            "id": product.id,
            "name": product.name,
            "url": product.get_absolute_url(),
            "image_url": product.image.url,
            "similarity": round(float(scores[row]), 4),
            "price": format_idr(product.price),
            "stock": product.stock,
        })
    return results
