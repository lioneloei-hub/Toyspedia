"""
This is a visual similarity search.

Model: facebook/dinov2-small -> 384-number embedding per image (the CLS
token from the final hidden layer, i.e. the model's summary of the whole
image).

Setup (one-time, needs internet):
    pip install torch torchvision transformers pillow

First call to compute_embedding() downloads the ~90MB model weights from
Hugging Face and caches them locally (~/.cache/huggingface). Every call
after that — including every real search — runs fully offline.
"""

from pathlib import Path
from typing import List, Union

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel

MODEL_NAME = "facebook/dinov2-small"
EMBEDDING_SIZE = 384  # dinov2-small's hidden size

_processor = None
_model = None


def _load_model():
    """Load the processor + model once, reuse for every embedding call."""
    global _processor, _model
    if _model is None:
        _processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
        _model = AutoModel.from_pretrained(MODEL_NAME)
        _model.eval()
    return _processor, _model


def compute_embedding(image_source: Union[str, Path, Image.Image]) -> List[float]:
    """
    Run one photo through DINOv2 and return its 384-number embedding.
    `image_source` is a product's `image_path` (or an already-open PIL
    Image, e.g. an uploaded photo held in memory).
    """
    processor, model = _load_model()

    if isinstance(image_source, Image.Image):
        img = image_source.convert("RGB")
    else:
        img = Image.open(image_source).convert("RGB")

    inputs = processor(images=img, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)

    # The CLS token (position 0) is DINOv2's whole-image summary vector.
    cls_embedding = outputs.last_hidden_state[:, 0, :].squeeze(0)
    return cls_embedding.tolist()
