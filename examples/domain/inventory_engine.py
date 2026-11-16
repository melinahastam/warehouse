"""Selected verbatim excerpt from the production inventory domain module.

Product and KardexEntry model definitions are intentionally omitted. This file
shows the real row-locking, invariant validation, balance update, and audit-entry
creation flow. It is a review artifact, not a standalone module.
"""

from django.core.exceptions import ValidationError


def _lock_products_for_update(product_ids):
    return {
        product.id: product
        for product in Product.objects.select_for_update().filter(id__in=sorted(set(product_ids))).order_by('id')
    }


def _persist_locked_product(product):
    if product.stock < 0:
        raise ValidationError(f'موجودی کالا نمی‌تواند منفی شود: {product.name}')
    if product.reserved_stock < 0 or product.allocated_stock < 0:
        raise ValidationError(f'وضعیت رزرو/تخصیص کالا نامعتبر است: {product.name}')
    if product.available_stock < 0:
        raise ValidationError(f'موجودی آزاد کالا نمی‌تواند منفی شود: {product.name}')
    product.save(update_fields=['stock', 'reserved_stock', 'allocated_stock'])


def _apply_inventory_movements(*, rows, doc_type, occurred_at, warehouse_doc=None, stock_transaction=None):
    if warehouse_doc is None and stock_transaction is None:
        raise ValueError('Inventory movement requires a source document.')
    if warehouse_doc is not None and stock_transaction is not None:
        raise ValueError('Inventory movement must have a single source.')

    locked_products = _lock_products_for_update([row['product_id'] for row in rows])
    kardex_entries = []

    for row in rows:
        product = locked_products[row['product_id']]
        quantity = int(row['quantity'])
        if quantity <= 0:
            raise ValidationError(f'مقدار عملیات برای {product.name} باید بیشتر از صفر باشد.')

        release_reserved = int(row.get('release_reserved', 0) or 0)
        release_allocated = int(row.get('release_allocated', 0) or 0)
        if product.reserved_stock < release_reserved:
            raise ValidationError(f'موجودی رزرو شده برای {product.name} کافی نیست.')
        if product.allocated_stock < release_allocated:
            raise ValidationError(f'موجودی تخصیص داده شده برای {product.name} کافی نیست.')

        delta = quantity if doc_type == 'IN' else -quantity
        next_stock = product.stock + delta
        if next_stock < 0:
            raise ValidationError(f'موجودی کافی نیست: {product.name}')

        product.stock = next_stock
        if release_reserved:
            product.reserved_stock -= release_reserved
        if release_allocated:
            product.allocated_stock -= release_allocated
        _persist_locked_product(product)

        kardex_entries.append(
            KardexEntry(
                product=product,
                occurred_at=occurred_at,
                transaction_type=doc_type,
                quantity_delta=delta,
                balance_after=product.stock,
                warehouse_doc=warehouse_doc,
                stock_transaction=stock_transaction,
            )
        )

    KardexEntry.objects.bulk_create(kardex_entries)

