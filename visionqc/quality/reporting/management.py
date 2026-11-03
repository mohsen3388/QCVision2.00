from __future__ import annotations


def build_management_summary(result: dict) -> str:
    status = result.get('status', 'نامشخص')
    final = float(result.get('final_score', 0))
    product = float(result.get('product_health', 0))
    process = float(result.get('process_health', 0))
    metrics = [m for m in result.get('metrics', []) if m.get('score') is not None and m.get('status') == 'OK']
    weak = sorted(metrics, key=lambda x: float(x.get('score', 100)))[:3]
    active = result.get('active_triggers', [])

    if final >= 90:
        decision = 'ادامه تولید توصیه می‌شود.'
        action = 'پایش معمول فرایند کافی است.'
    elif final >= 80:
        decision = 'ادامه تولید با پایش بیشتر مجاز است.'
        action = 'شاخص‌های ضعیف در دو دقیقه آینده بررسی شوند.'
    elif final >= 70:
        decision = 'بررسی اپراتور پیش از ادامه فرایند توصیه می‌شود.'
        action = 'تنظیمات فرایند و وضعیت محصول بازبینی شوند.'
    elif final >= 50:
        decision = 'ادامه فرایند بدون اقدام اصلاحی توصیه نمی‌شود.'
        action = 'اپراتور و مدیر QC فوراً بررسی کنند.'
    else:
        decision = 'توقف موقت و ارزیابی فوری توصیه می‌شود.'
        action = 'محصول و تجهیزات پیش از راه‌اندازی مجدد تأیید شوند.'

    if active:
        reasons = '\n'.join(f"• {x.get('problem_text') or x.get('name')}" for x in active[:3])
    else:
        reasons = '\n'.join(f"• {m.get('name', m.get('key'))}: {float(m.get('score', 0)):.0f}/100" for m in weak if float(m.get('score', 100)) < 80)
        if not reasons:
            reasons = '• شاخص معناداری خارج از محدوده مشاهده نشد.'

    assessability = result.get('image_assessability')
    assessability_line = '' if assessability is None else f"\nقابلیت ارزیابی تصویر: {float(assessability):.1f}/100"
    note = '\n\nمحدودیت: تحلیل تصویر، شاخص پشتیبان تصمیم‌گیری است و برای استفاده عملیاتی باید با نمونه‌های تأییدشده همان کارخانه کالیبره شود.'
    return f"وضعیت کلی: {status}\nسلامت محصول: {product:.1f}/100\nسلامت فرایند: {process:.1f}/100{assessability_line}\nامتیاز تصمیم: {final:.1f}/100\n\nتصمیم نهایی: {decision}\n\nدلایل اصلی:\n{reasons}\n\nاقدام پیشنهادی: {action}{note}"
