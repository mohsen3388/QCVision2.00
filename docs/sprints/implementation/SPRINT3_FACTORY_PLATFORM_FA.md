# VisionQC 4.2 — Sprint 3 Factory Platform

این Sprint یک نمای عملیاتی سطح کارخانه به محصول اضافه می‌کند و داده‌های Camera Registry و Runtime Event Repository را در یک مدل واحد تجمیع می‌کند.

## قابلیت‌های افزوده‌شده

- سرویس `FactoryMonitoringService` برای تجمیع دوربین‌ها، سلامت، رخدادهای باز و شدت بیشینه.
- صفحه فارسی `Factory Operations Dashboard` با الگوی Overview/Problems آشنا برای کاربران Zabbix.
- نمایش سلامت میانگین کارخانه، تعداد دوربین‌های فعال، دوربین‌های رخداددار، رخدادهای فعال و هشدارهای High/Critical.
- فیلتر بر اساس پروفایل و جست‌وجوی ناحیه، دستگاه و رخداد.
- حفظ کامل Factory Camera Center، Runtime Operations، Studio، Voice AI و قابلیت‌های قبلی.

## منطق تصمیم

رخداد باز High یا Critical بر وضعیت ظاهری دوربین اولویت دارد. در نبود رخداد، وضعیت دوربین از Health Score تعیین می‌شود.
