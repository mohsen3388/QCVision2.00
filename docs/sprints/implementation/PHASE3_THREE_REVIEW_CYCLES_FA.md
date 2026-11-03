
# سه دور بازبینی تخصصی فاز سوم

## دور اول — Runtime و Zabbix
- Assignment مستقل Camera/Host به Template Production افزوده شد.
- Item History، Trigger evaluation، Problem/Event، Action log و Acknowledge پیاده‌سازی شد.
- Runtime از Studio جدا شد و Template غیر Production را اجرا نمی‌کند.

## دور دوم — فرایند و صنایع غذایی
- هر دوربین فقط Template تخصیص‌یافته را اجرا می‌کند.
- تاریخچه هر شاخص مستقل ذخیره می‌شود و Trigger می‌تواند last/avg/median/min/max/slope/count را ارزیابی کند.
- Persistence و Recovery برای جلوگیری از هشدار تک‌فریم اعمال شد.
- شواهد هر رخداد همراه مقدار، تابع، آستانه و نتیجه شرط ثبت می‌شود.

## دور سوم — برنامه‌نویسی، پایداری و بهره‌برداری
- Worker مستقل برای File/USB/RTSP ساخته شد.
- توقف Worker، آزادسازی VideoCapture، Production Gate، Diagnostics و Audit عملیاتی بررسی شد.
- SQLite indexes برای تاریخچه و رخدادها اضافه شد.
- تست Assignment، Production Gate، ذخیره History و ایجاد Event افزوده شد.
