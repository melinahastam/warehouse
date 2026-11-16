"""Selected real methods from the WarehouseDoc domain model.

Model fields, choice declarations, and unrelated helpers are intentionally
withheld. The validation and posting flow is preserved for technical review.
"""

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone


class WarehouseDoc(models.Model):
    """Excerpt of reference validation and atomic posting behavior."""

    def _aggregated_item_quantities(self, items):
        totals = {}
        for item in items:
            totals[item.product_id] = totals.get(item.product_id, 0) + item.quantity
        return totals

    def _validate_against_reference_invoice(self, items):
        if self.reference_purchase_id and not self.return_type:
            expected = {
                item.product_id: item.quantity
                for item in self.reference_purchase.items.select_related('product').order_by('id')
            }
            if self._aggregated_item_quantities(items) != expected:
                raise ValidationError('رسید خرید باید دقیقاً مطابق اقلام فاکتور خرید باشد.')

        if self.reference_sales_id and not self.return_type:
            expected = {
                item.product_id: item.quantity
                for item in self.reference_sales.items.select_related('product').order_by('id')
            }
            if self._aggregated_item_quantities(items) != expected:
                raise ValidationError('حواله فروش باید دقیقاً مطابق اقلام سفارش فروش باشد.')

        if not self.return_type:
            return

        source_invoice = self.reference_purchase if self.return_type == 'PURCHASE' else self.reference_sales
        source_totals = {
            item.product_id: item.quantity
            for item in source_invoice.items.select_related('product').order_by('id')
        }
        posted_returns = WarehouseDoc.objects.filter(
            status=WarehouseDocStatus.POSTED,
            return_type=self.return_type,
        ).exclude(pk=self.pk)
        if self.return_type == 'PURCHASE':
            posted_returns = posted_returns.filter(reference_purchase=source_invoice)
        else:
            posted_returns = posted_returns.filter(reference_sales=source_invoice)

        returned_totals = {
            row['product_id']: row['total_qty']
            for row in posted_returns.values('items__product_id').annotate(
                product_id=models.F('items__product_id'),
                total_qty=Sum('items__quantity'),
            )
        }
        for product_id, quantity in self._aggregated_item_quantities(items).items():
            remaining = source_totals.get(product_id, 0) - (returned_totals.get(product_id, 0) or 0)
            if quantity > remaining:
                raise ValidationError('مقدار برگشت از سقف مجاز سند مرجع بیشتر است.')

    def _validate_against_count_session(self, items):
        if not self.count_session_id:
            return
        if self.adjustment_reason not in {'COUNT_SHORTAGE', 'COUNT_OVERAGE'}:
            raise ValidationError('اسناد مبتنی بر انبارگردانی فقط با کسری یا اضافی شمارش معتبر هستند.')

        scanned_totals = {
            row['product_id']: row['total_scanned']
            for row in self.count_session.scan_records.values('product_id').annotate(total_scanned=Sum('scanned_quantity'))
        }
        expected = {}
        for session_item in self.count_session.items.select_related('product').all():
            difference = (scanned_totals.get(session_item.product_id, 0) or 0) - session_item.expected_stock
            if self.adjustment_reason == 'COUNT_SHORTAGE' and difference < 0:
                expected[session_item.product_id] = abs(difference)
            if self.adjustment_reason == 'COUNT_OVERAGE' and difference > 0:
                expected[session_item.product_id] = difference

        if self._aggregated_item_quantities(items) != expected:
            raise ValidationError('اقلام سند تعدیل باید دقیقاً مطابق مغایرت جلسه انبارگردانی باشد.')

    @transaction.atomic
    def post(self, *, user=None):
        self.refresh_from_db()
        if self.status == WarehouseDocStatus.POSTED:
            return
        if self.status == WarehouseDocStatus.CANCELED:
            raise ValidationError('سند ابطال شده قابل ثبت نهایی نیست.')

        self.full_clean()
        items = list(self.items.select_related('product').order_by('product_id', 'id'))
        if not items:
            raise ValidationError('سند بدون قلم قابل ثبت نهایی نیست.')

        for item in items:
            item.full_clean()

        self._validate_against_reference_invoice(items)
        self._validate_against_count_session(items)

        rows = []
        for item in items:
            row = {'product_id': item.product_id, 'quantity': item.quantity}
            if self.reference_sales_id and self.doc_type == 'OUT' and not self.return_type:
                row['release_allocated'] = item.quantity
            rows.append(row)

        _apply_inventory_movements(
            rows=rows,
            doc_type=self.doc_type,
            occurred_at=timezone.now(),
            warehouse_doc=self,
        )

        if self.reference_sales_id and self.doc_type == 'OUT':
            self.reference_sales.mark_as_shipped_after_inventory_release()
        if self.reference_purchase_id and self.doc_type == 'IN' and not self.return_type:
            self.reference_purchase.mark_as_received()

        if user is not None and not self.created_by_id:
            self.created_by = user

        self.status = WarehouseDocStatus.POSTED
        self.save(update_fields=['status', 'created_by', 'updated_at'])

