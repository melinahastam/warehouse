"""Real excerpt of the sales inventory-commitment workflow.

Unrelated model fields and methods are omitted. The transition rules and method
bodies below are taken from the operational domain model.
"""

from django.core.exceptions import ValidationError
from django.db import models, transaction


SALES_STATUS_TRANSITIONS = {
    'PROFORMA': ['ORDER'],
    'ORDER': ['PROFORMA', 'APPROVED'],
    'APPROVED': ['ORDER'],
    'SHIPPED': ['DELIVERED'],
    'DELIVERED': ['SETTLED'],
    'SETTLED': [],
}


class SalesInvoice(models.Model):
    """Excerpt: model fields and unrelated methods are intentionally omitted."""

    def _bucket_for_status(self, status):
        if status == InvoiceStatus.ORDER:
            return 'reserved'
        if status == InvoiceStatus.APPROVED:
            return 'allocated'
        return None

    def item_quantities(self):
        return [{'product_id': item.product_id, 'quantity': item.quantity} for item in self.items.all()]

    @transaction.atomic
    def move_inventory_commitment(self, old_status, new_status, *, quantities=None):
        quantities = self.item_quantities() if quantities is None else quantities
        old_bucket = self._bucket_for_status(old_status)
        new_bucket = self._bucket_for_status(new_status)
        if old_bucket == new_bucket or not quantities:
            return

        SalesInvoice.objects.select_for_update().get(pk=self.pk)
        locked_products = _lock_products_for_update([row['product_id'] for row in quantities])

        if old_bucket is None and new_bucket is not None:
            for row in quantities:
                product = locked_products[row['product_id']]
                if product.available_stock < row['quantity']:
                    raise ValidationError(f'موجودی آزاد کافی نیست: {product.name}')
                setattr(product, f'{new_bucket}_stock', getattr(product, f'{new_bucket}_stock') + row['quantity'])
                _persist_locked_product(product)
            return

        if old_bucket is not None and new_bucket is None:
            for row in quantities:
                product = locked_products[row['product_id']]
                if getattr(product, f'{old_bucket}_stock') < row['quantity']:
                    raise ValidationError(f'موجودی تعهدشده برای {product.name} کافی نیست.')
                setattr(product, f'{old_bucket}_stock', getattr(product, f'{old_bucket}_stock') - row['quantity'])
                _persist_locked_product(product)
            return

        for row in quantities:
            product = locked_products[row['product_id']]
            if getattr(product, f'{old_bucket}_stock') < row['quantity']:
                raise ValidationError(f'موجودی تعهدشده برای {product.name} کافی نیست.')
            setattr(product, f'{old_bucket}_stock', getattr(product, f'{old_bucket}_stock') - row['quantity'])
            setattr(product, f'{new_bucket}_stock', getattr(product, f'{new_bucket}_stock') + row['quantity'])
            _persist_locked_product(product)

    @transaction.atomic
    def transition_status(self, new_status):
        allowed = SALES_STATUS_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValidationError('این تغییر وضعیت برای سفارش فروش مجاز نیست.')
        previous_status = self.status
        self.move_inventory_commitment(previous_status, new_status)
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])

