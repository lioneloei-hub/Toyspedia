"""
chatbot.py - the Toyspedia customer-service bot (final version).

The same three ideas as the teaching kit:
  1. Python finds the products the customer is talking about (keyword match).
  2. Only those rows go into the prompt, never the whole catalogue.
  3. The LLM answers using just those rows.

Buying: when the customer confirms, the LLM replies with one line
"BUY <product id> <quantity>". Python checks that line and acts on it.
The bot never changes stock itself. It adds the item to the logged-in
customer's cart, and the normal checkout page creates the order.
"""

import logging
import re
import unicodedata

from django.conf import settings
from django.db import transaction
from openai import OpenAI

from .formatting import format_idr
from .models import Cart, CartItem, Product

logger = logging.getLogger(__name__)

MAX_PRODUCTS_IN_PROMPT = 15   # keeps each request small
MAX_HISTORY = 10              # only the last 10 messages go to the model
MAX_QUANTITY = 99             # one chat message can't ask for more than this

STOPWORDS = {
    "the", "and", "for", "you", "your", "have", "has", "what", "which", "how",
    "much", "many", "price", "cost", "stock", "available", "want", "buy",
    "need", "there", "any", "with", "this", "that", "does", "can", "please",
    "are", "still", "yes", "order", "get", "left", "sell", "one", "some",
    "about", "like", "would", "could", "tell", "show", "from", "all", "its",
}

# The model must answer with exactly this line to buy. Anything else is a normal reply.
BUY_LINE = re.compile(r"\s*BUY\s+(\d+)\s+(\d+)\s*\.?\s*")


class ChatbotUnavailable(Exception):
    """The LLM can't be reached, or no API key is set."""


# ---------- 1. Find relevant products ----------

def normalize(text):
    """'Pokémon Card!' -> ['pokemon', 'card']  (lowercase, no accents, words only)."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", text.lower())


def active_products():
    return Product.objects.filter(is_active=True).select_related("category")


def find_relevant_products(text, products):
    words = {w for w in normalize(text)
             if w not in STOPWORDS and (len(w) >= 3 or w.isdigit())}
    if not words:
        return []

    scored = []
    for p in products:
        name_hits = len(words & set(normalize(p.name)))
        category_hits = len(words & set(normalize(p.category.name)))
        score = name_hits * 2 + category_hits  # a name match counts more
        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [p for _, p in scored[:MAX_PRODUCTS_IN_PROMPT]]


# ---------- 2. Build the prompt ----------

def build_system_prompt(found):
    if found:
        rows = "\n".join(
            f"{p.id} | {p.name} | {p.category.name} | {format_idr(p.price)} | stock {p.stock}"
            for p in found
        )
    else:
        rows = "(no matching products found)"

    return f"""You are the friendly customer service assistant for Toyspedia,
an online toy store (LEGO, Gunpla, Pokémon cards, games and more). Prices are in Indonesian Rupiah.

Rules:
- Answer ONLY using the product list below. Never invent products, prices or stock.
- If the product isn't in the list, say you couldn't find it and ask for the exact name.
- Keep answers short.

Buying:
- Before a purchase, confirm the product, quantity and total price with the customer.
- When the customer clearly confirms, reply with exactly this one line and nothing else:
BUY <product id> <quantity>
(for example: BUY 97 2)

Product list (id | name | category | price | stock):
{rows}"""


# ---------- 3. Call the LLM ----------

def ask_llm(system_prompt, messages):
    """Send the prompt and the conversation to Groq. Returns the reply text."""
    if not settings.GROQ_API_KEY:
        raise ChatbotUnavailable("GROQ_API_KEY is not set.")

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.GROQ_API_KEY,
        timeout=30,
    )
    response = client.chat.completions.create(
        model=settings.CHATBOT_MODEL,
        messages=[{"role": "system", "content": system_prompt}] + messages,
        reasoning_effort="low",  # gpt-oss "thinks" first; low = faster, fewer tokens
    )
    return response.choices[0].message.content or ""


# ---------- 4. Purchase: add to the customer's cart ----------

def add_to_cart(user, product_id, quantity):
    """Put a product in this customer's cart. Returns the message the customer sees."""
    if quantity < 1 or quantity > MAX_QUANTITY:
        return f"Please choose a quantity between 1 and {MAX_QUANTITY}."

    with transaction.atomic():
        product = Product.objects.select_for_update().filter(pk=product_id, is_active=True).first()
        if product is None:
            return "Sorry, I couldn't find that product."
        if product.stock <= 0:
            return f"Sorry, {product.name} is sold out."
        if quantity > product.stock:
            return f"Sorry, only {product.stock} of {product.name} left in stock."

        cart, _ = Cart.objects.get_or_create(user=user)
        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, defaults={"quantity": quantity},
        )
        if not created:
            new_quantity = item.quantity + quantity
            if new_quantity > product.stock:
                return (f"You already have {item.quantity} in your cart, and only "
                        f"{product.stock} of {product.name} are in stock.")
            item.quantity = new_quantity
            item.save(update_fields=["quantity"])

    total = format_idr(product.price * quantity)
    return (f"I added {quantity} x {product.name} ({total}) to your cart. "
            f"Open your cart to check out.")


# ---------- 5. The main function the website calls ----------

def chat(messages, user=None):
    """
    messages: the whole conversation, e.g.
        [{"role": "user", "content": "Do you have Pikachu?"},
         {"role": "assistant", "content": "Yes! ..."},
         {"role": "user", "content": "How much is it?"}]
    user: the logged-in customer, or None for a visitor.
    Returns the bot's reply as text.
    """
    products = list(active_products())  # read fresh, so stock changes show up

    # Search the last 3 user messages, so "how much is it?" still finds
    # the Pikachu mentioned one message earlier.
    recent_user_text = " ".join(
        [m["content"] for m in messages if m["role"] == "user"][-3:]
    )
    found = find_relevant_products(recent_user_text, products)

    reply = ask_llm(build_system_prompt(found), messages[-MAX_HISTORY:])

    match = BUY_LINE.fullmatch(reply)
    if match:
        if user is None or not user.is_authenticated:
            return "Please log in first, and then I can add that to your cart."
        return add_to_cart(user, int(match.group(1)), int(match.group(2)))
    return reply
