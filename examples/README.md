# نمونه‌کدهای منتخب

این پوشه شامل excerptهای واقعی از پروژه اصلی Smart Inventory است. نام متدها، قواعد دامنه و جریان‌های اصلی از کد عملیاتی انتخاب شده‌اند و برای ساخت Showcase از نو نوشته نشده‌اند.

برای حفظ مالکیت فکری:

- فایل‌ها بخشی محدود از ماژول اصلی هستند؛
- بعضی importها، fieldها، helperها و بخش‌های غیرمرتبط حذف شده‌اند؛
- این مجموعه یک نسخه قابل اجرا یا قابل استقرار از محصول نیست؛
- داده، Secret، تنظیمات Production و منطق کامل رابط کاربری در اینجا وجود ندارد.

## مسیر پیشنهادی بررسی

1. [`domain/inventory_engine.py`](domain/inventory_engine.py): هسته تغییر موجودی و کاردکس
2. [`domain/sales_commitment.py`](domain/sales_commitment.py): رزرو و تخصیص در State Machine فروش
3. [`domain/warehouse_posting.py`](domain/warehouse_posting.py): ثبت نهایی سند و کنترل سند مرجع
4. [`domain/inventory_counting.py`](domain/inventory_counting.py): Snapshot و Scan Validation
5. [`security/rbac.py`](security/rbac.py): کنترل دسترسی Role/Permission
6. [`tests/test_inventory_workflow.py`](tests/test_inventory_workflow.py): اثبات رفتاری جریان فروش تا کاردکس

هر فایل با توضیح محدوده excerpt شروع می‌شود.

