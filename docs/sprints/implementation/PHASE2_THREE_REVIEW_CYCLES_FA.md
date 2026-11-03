# VisionQC 3.0 — سه دور بازبینی تخصصی فاز دوم

## دور اول: هم‌ترازی با الگوی Zabbix
اعضا: متخصص Zabbix، معمار نرم‌افزار، مهندس کیفیت، متخصص صنایع غذایی، مهندس بینایی ماشین.

### ایرادهای شناسایی‌شده
- کاربر Zabbix باید مسیر Template → Item → Trigger → Action را بدون یادگیری مفاهیم تازه تشخیص دهد.
- هر Item باید الزاماً به Detector واقعی متصل باشد.
- نبود داده نباید با امتیاز صفر اشتباه شود.
- انتشار مستقیم تنظیمات آزمایش‌نشده خطرناک است.

### اصلاحات اعمال‌شده
- نام‌گذاری دوگانه Zabbix/Food Quality در UI.
- Detector Registry اجباری و Validation اتصال Metric به Detector.
- Lifecycle شامل Draft، Testing، Validated و Production.
- Dry Run بدون اجرای Action واقعی.

## دور دوم: بازبینی علمی و فرایندی صنایع غذایی

### ایرادهای شناسایی‌شده
- وزن کیفیت محصول و فرایند باید جدا باشد.
- شاخص‌های عکس نباید ادعای زمانی داشته باشند.
- یک شاخص منفرد نباید خرابی محصول را قطعی اعلام کند.
- اقدامات باید قابل ویرایش، مرحله‌ای و دارای تأیید اپراتور باشند.

### اصلاحات اعمال‌شده
- گروه‌های «سلامت محصول» و «سلامت فرایند» و وزن مستقل.
- Scoring قابل تنظیم: Higher/Lower/Ideal Range.
- Triggerهای چندشرطی و Persistence.
- Action Steps با Target، Delay، Repeat و Acknowledgement.
- Template مرجع «اختلاط خمیر سوسیس» با شاخص‌ها، Triggerها و اقدامات نمونه.

## دور سوم: بازبینی قابلیت اجرا و نگهداشت نرم‌افزار

### ایرادهای شناسایی‌شده
- پردازش تکراری تصویر برای هر شاخص مصرف CPU را بالا می‌برد.
- باید امکان Export/Import، Audit و Diagnostics وجود داشته باشد.
- انتشار Production باید در صورت وزن نامعتبر یا Detector مفقود متوقف شود.
- تست باید هم عکس و هم ویدئو را پوشش دهد.

### اصلاحات اعمال‌شده
- Runtime مشترک برای Image/Video و نمونه‌برداری ویدئو هر دو ثانیه.
- SQLite Repository، Audit Log و Validation Run.
- Diagnostics با وضعیت RUNNING/ERROR برای هر Item.
- Export/Import JSON و Production Gate.
- مجموعه تست‌های رگرسیون هسته فاز دوم.

## نتیجه نهایی جلسه سوم
فاز دوم برای استفاده به‌عنوان Configuration Core و نمونه عملی VisionQC Studio پذیرفته شد. اتصال کامل Runtime دوربین‌های عملیاتی به Templateهای Production در فاز سوم انجام می‌شود؛ اما Detector Registry، Metric/Item Builder، Trigger Builder، Action Builder، Template Builder و Dry Run در این نسخه عملیاتی هستند.
