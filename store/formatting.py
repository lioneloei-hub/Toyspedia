def format_idr(amount):
    """Format a number as Indonesian Rupiah, e.g. 11643742.95 -> 'Rp 11.643.743'."""
    return f"Rp {int(round(float(amount))):,}".replace(",", ".")
