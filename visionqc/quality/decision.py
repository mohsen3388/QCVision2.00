from __future__ import annotations


def status_for(score: float) -> str:
    return 'پایدار' if score >= 90 else 'نیاز به پایش' if score >= 80 else 'هشدار سطح متوسط' if score >= 70 else 'هشدار سطح بالا' if score >= 50 else 'بحرانی'


def fuse(product: float, process: float, *, product_weight: float = 75, process_weight: float = 25, assessability: float | None = None, critical_override: bool = False) -> tuple[float, str]:
    final = (product * product_weight + process * process_weight) / max(1.0, product_weight + process_weight)
    # Product quality is the limiting dimension; a stable machine cannot hide a poor product.
    if product < 50: final = min(final, 49.0)
    elif product < 70: final = min(final, 69.0)
    elif product < 80: final = min(final, 79.0)
    # Poor assessability lowers confidence, but does not falsely classify the product as defective.
    if assessability is not None and assessability < 40:
        final = min(final, 79.0)
    if critical_override:
        final = min(final, 49.0)
    return round(float(final), 2), status_for(float(final))
