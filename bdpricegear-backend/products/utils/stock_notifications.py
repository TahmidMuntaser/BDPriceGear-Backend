from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from products.models import StockSubscription


def _build_stock_email(product):
    subject = f"{product.name} is back in stock"
    product_url = product.product_url or ''
    shop_name = product.shop.name if product.shop_id else 'our store'
    price_text = f"{product.currency} {product.current_price}" if product.current_price is not None else 'the current price'

    text_body = (
        f"Good news! {product.name} is back in stock at {shop_name}.\n\n"
        f"Current price: {price_text}\n"
        f"Product link: {product_url}\n\n"
        "You asked to be notified when this product returned to stock."
    )

    html_body = (
        f"<p>Good news! <strong>{product.name}</strong> is back in stock at {shop_name}.</p>"
        f"<p><strong>Current price:</strong> {price_text}</p>"
        f"<p><a href=\"{product_url}\">View product</a></p>"
        "<p>You asked to be notified when this product returned to stock.</p>"
    )

    return subject, text_body, html_body


def send_back_in_stock_notifications(product_ids):
    if not product_ids:
        return {'products': 0, 'subscriptions': 0, 'sent': 0, 'failed': 0}

    subscriptions = (
        StockSubscription.objects.filter(
            product_id__in=product_ids,
            notified_at__isnull=True,
        )
        .select_related('user', 'product', 'product__shop')
        .order_by('created_at')
    )

    sent_subscription_ids = []
    failed = 0
    processed_products = set()

    for subscription in subscriptions:
        product = subscription.product
        subject, text_body, html_body = _build_stock_email(product)
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[subscription.user.email],
        )
        email.attach_alternative(html_body, 'text/html')

        try:
            email.send(fail_silently=False)
        except Exception:
            failed += 1
            continue

        sent_subscription_ids.append(subscription.id)
        processed_products.add(product.id)

    if sent_subscription_ids:
        StockSubscription.objects.filter(id__in=sent_subscription_ids).delete()

    return {
        'products': len(processed_products),
        'subscriptions': subscriptions.count(),
        'sent': len(sent_subscription_ids),
        'failed': failed,
    }