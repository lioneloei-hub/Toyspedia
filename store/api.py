"""
api.py - the two JSON endpoints the page calls.

    POST /products/api/chat/    {"messages": [...]}  -> {"reply": "..."}
    POST /products/api/search/  multipart with "image" -> {"results": [...]}

Never trust the browser: every field is checked here, even though our own
page always sends good data.
"""

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from PIL import Image

from .chatbot import MAX_HISTORY, chat
from .image_search import IndexNotReady, search

logger = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 1000


def _error(message, status):
    return JsonResponse({"error": message}, status=status)


@require_POST
def api_chat(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        return _error('Send JSON like {"messages": [...]}', 400)

    # Keep only user/assistant messages, and cap the length of each one.
    messages = []
    for m in data["messages"][-MAX_HISTORY:]:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            continue
        content = str(m.get("content", "")).strip()[:MAX_MESSAGE_CHARS]
        if content:
            messages.append({"role": m["role"], "content": content})

    if not messages or messages[-1]["role"] != "user":
        return _error("The last message must be from the user.", 400)

    try:
        reply = chat(messages, user=request.user)
    except Exception:
        logger.exception("Chat failed")  # the details go to our log, not the customer
        return _error("The chatbot is unavailable right now. Please try again.", 502)
    return JsonResponse({"reply": reply})


@require_POST
def api_search(request):
    upload = request.FILES.get("image")
    if upload is None:
        return _error("Please choose an image to upload.", 400)
    if upload.size > settings.MAX_IMAGE_UPLOAD_BYTES:
        return _error("Image is too large (max 5 MB).", 413)

    try:
        image = Image.open(upload)
        image.load()  # read the whole file now, so a broken file fails here
    except (Image.UnidentifiedImageError, Image.DecompressionBombError, OSError):
        return _error("That file isn't an image.", 400)

    try:
        results = search(image, top_n=3)
    except IndexNotReady:
        return _error("Image search isn't ready yet. Ask the shop to run build_embeddings.", 503)
    except Exception:
        logger.exception("Image search failed")
        return _error("Image search is unavailable right now. Please try again.", 502)
    return JsonResponse({"results": results})
