"""Real excerpt of snapshot-based inventory counting.

Imports and neighboring models not needed for review are intentionally omitted.
"""

from django.core.exceptions import ValidationError
from django.db import models, transaction


class InventoryCountSessionStatus(models.TextChoices):
    OPEN = 'OPEN', 'باز'
    CLOSED = 'CLOSED', 'بسته'
    POSTED = 'POSTED', 'تعدیل‌سازی شده'


class InventoryCountSession(models.Model):
    """Excerpt: fields and display metadata are omitted."""

    @property
    def total_scanned_quantity(self):
        return sum(item.scanned_quantity for item in self.scan_records.all())

    @transaction.atomic
    def initialize_snapshot(self):
        if self.items.exists():
            return
        InventoryCountSessionItem.objects.bulk_create([
            InventoryCountSessionItem(
                session=self,
                product=product,
                expected_stock=product.stock,
            )
            for product in Product.objects.filter(project=self.project).order_by('id')
        ])


class ScanRecord(models.Model):
    """Excerpt: field declarations are omitted; validation is unchanged."""

    def clean(self):
        if self.product_id and self.project_id and self.product.project_id != self.project_id:
            raise ValidationError('کالای اسکن‌شده باید متعلق به همان پروژه باشد.')
        if self.count_session_id:
            if self.count_session.project_id != self.project_id:
                raise ValidationError('جلسه شمارش و پروژه اسکن باید یکسان باشند.')
            if self.count_session.status != InventoryCountSessionStatus.OPEN:
                raise ValidationError('فقط در جلسه شمارش باز می‌توان اسکن ثبت کرد.')

