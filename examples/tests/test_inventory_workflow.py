"""Selected real behavior test from the main Django test suite.

The project models are intentionally not distributed in this showcase, so this
file documents the tested workflow rather than serving as a standalone test.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from scanner.models import (
    InventoryProject,
    InvoiceStatus,
    KardexEntry,
    Party,
    Product,
    SalesInvoice,
    SalesInvoiceItem,
)


class InventorySalesWorkflowTests(TestCase):
    def setUp(self):
        self.project = InventoryProject.objects.create(title='Main Project')
        self.user = User.objects.create_user(username='operator', password='pass12345')
        self.customer = Party.objects.create(name='Customer', party_type='CUSTOMER')
        self.product = Product.objects.create(
            project=self.project,
            barcode='2001',
            code='SKU-2001',
            name='Widget',
            stock=5,
        )

    def test_sales_workflow_releases_commitment_on_shipping(self):
        invoice = SalesInvoice.objects.create(
            project=self.project,
            party=self.customer,
            invoice_no='SO-1',
            invoice_date=timezone.localdate(),
            status=InvoiceStatus.PROFORMA,
            created_by=self.user,
        )
        SalesInvoiceItem.objects.create(invoice=invoice, product=self.product, quantity=3, unit_price=10)

        invoice.transition_status(InvoiceStatus.ORDER)
        self.product.refresh_from_db()
        self.assertEqual(self.product.reserved_stock, 3)
        self.assertEqual(self.product.allocated_stock, 0)

        invoice.transition_status(InvoiceStatus.APPROVED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.reserved_stock, 0)
        self.assertEqual(self.product.allocated_stock, 3)

        doc = invoice.issue_to_warehouse(user=self.user)
        doc.post(user=self.user)

        invoice.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.SHIPPED)
        self.assertEqual(self.product.stock, 2)
        self.assertEqual(self.product.allocated_stock, 0)
        self.assertTrue(KardexEntry.objects.filter(warehouse_doc=doc, product=self.product).exists())

