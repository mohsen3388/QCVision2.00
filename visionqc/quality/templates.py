from __future__ import annotations
from visionqc.configuration.models import *


def _metric(key,name,detector,group,weight,mode='higher_is_better',**kwargs):
    scoring=ScoringRule(mode=mode,raw_min=0,raw_max=1,ideal_low=kwargs.get('ideal_low'),ideal_high=kwargs.get('ideal_high'),tolerance=kwargs.get('tolerance',0))
    return MetricDefinition(key=key,name_fa=name,detector_key=detector,group_name=group,weight=weight,lifecycle='Validated',scoring=scoring,window_seconds=kwargs.get('window',30),persistence_seconds=kwargs.get('persistence',8),detector_params=kwargs.get('params',{}),notes=kwargs.get('notes',''))


def sausage_mixing_commercial_template()->InspectionTemplate:
    metrics=[
      _metric('product.texture','یکنواختی بافت','product.texture_uniformity','سلامت محصول',22),
      _metric('product.color','یکنواختی رنگ','product.color_uniformity','سلامت محصول',14),
      _metric('product.surface','سلامت سطح','product.surface_homogeneity','سلامت محصول',16),
      _metric('product.aeration','سلامت هوادهی','product.bubble_density','سلامت محصول',10,'lower_is_better'),
      _metric('product.golden_color','تطابق رنگ با مرجع','reference.color_similarity','سلامت محصول',14),
      _metric('product.golden_texture','تطابق بافت با مرجع','reference.texture_similarity','سلامت محصول',14),
      _metric('product.visual_homogeneity','همگنی ظاهری','image.edge_density','سلامت محصول',10,'ideal_range',ideal_low=.02,ideal_high=.18),
      _metric('process.motion','ثبات حرکت','process.motion_stability','سلامت فرایند',24,window=60),
      _metric('process.mixing_coverage','پوشش اختلاط','process.mixing_coverage','سلامت فرایند',24,window=60),
      _metric('process.dead_zone','سلامت نواحی کم‌تحرک','process.dead_zone_health','سلامت فرایند',20,window=60),
      _metric('process.temporal','ثبات زمانی فرایند','process.temporal_consistency','سلامت فرایند',20,window=60),
      _metric('process.assessability','قابلیت ارزیابی تصویر','image.assessability','سلامت فرایند',12),
    ]
    triggers=[
      TriggerDefinition('tr.texture.watch','افت بافت نیازمند پایش','نیاز به پایش','AND',[TriggerCondition('product.texture','avg','<',80,30)],8,lifecycle='Validated',problem_text='میانگین یکنواختی بافت از محدوده مطلوب خارج شده است.'),
      TriggerDefinition('tr.product.medium','افت چندشاخصی محصول','هشدار سطح متوسط','AND',[TriggerCondition('product.texture','avg','<',75,30),TriggerCondition('product.surface','avg','<',78,30)],10,lifecycle='Validated',problem_text='بافت و سطح محصول هم‌زمان در حال افت هستند.'),
      TriggerDefinition('tr.mixing.high','اختلاط ناکافی','هشدار سطح بالا','AND',[TriggerCondition('process.mixing_coverage','avg','<',65,60),TriggerCondition('process.dead_zone','avg','<',70,60),TriggerCondition('product.texture','avg','<',72,30)],10,lifecycle='Validated',problem_text='پوشش اختلاط ناکافی و ناحیه کم‌تحرک همراه با افت بافت مشاهده شده است.'),
      TriggerDefinition('tr.emulsion.high','ریسک ناپایداری امولسیون','هشدار سطح بالا','AND',[TriggerCondition('product.texture','avg','<',65,30),TriggerCondition('product.surface','avg','<',70,30),TriggerCondition('product.aeration','avg','<',70,30)],10,lifecycle='Validated',problem_text='چند شاهد مستقل، ناپایداری احتمالی محصول را تأیید می‌کنند.'),
      TriggerDefinition('tr.assessment.unreliable','تصویر غیرقابل اتکا','نیاز به پایش','AND',[TriggerCondition('process.assessability','last','<',40,10)],5,lifecycle='Validated',problem_text='کیفیت تصویر برای تصمیم قطعی کافی نیست.'),
    ]
    actions=[
      ActionDefinition('act.texture.watch','پایش افت بافت','tr.texture.watch',[ActionStep(1,'dashboard','مدیر QC','روند بافت را برای دو دقیقه آینده تحت نظر نگه دارید.')],lifecycle='Validated'),
      ActionDefinition('act.product.medium','بررسی اپراتوری','tr.product.medium',[ActionStep(1,'dashboard','مدیر QC','بررسی اپراتور توصیه می‌شود.'),ActionStep(2,'headset','اپراتور دیگ','هشدار کیفیت؛ بافت و سطح محصول را بررسی کنید.',require_ack=True),ActionStep(3,'snapshot','سیستم','ذخیره تصویر رخداد')],lifecycle='Validated'),
      ActionDefinition('act.mixing.high','اقدام اختلاط ناکافی','tr.mixing.high',[ActionStep(1,'dashboard','مدیر QC','پوشش اختلاط و مواد باقی‌مانده روی دیواره بررسی شود.'),ActionStep(2,'headset','اپراتور دیگ','هشدار سطح بالا؛ پوشش اختلاط، مواد روی دیواره و تنظیمات میکسر را بررسی کنید.',require_ack=True),ActionStep(3,'snapshot','سیستم','ذخیره شواهد رخداد'),ActionStep(4,'ai','مشاور هوشمند','بسته شاخص‌ها برای نظر تخصصی ارسال شود.')],lifecycle='Validated'),
      ActionDefinition('act.emulsion.high','اقدام ناپایداری امولسیون','tr.emulsion.high',[ActionStep(1,'dashboard','مدیر QC','ادامه فرایند بدون بررسی توصیه نمی‌شود.'),ActionStep(2,'headset','اپراتور دیگ','هشدار سطح بالا؛ دمای خمیر، زمان اختلاط و خلأ را بررسی کنید.',require_ack=True),ActionStep(3,'ai','مشاور هوشمند','بسته شاخص‌ها برای نظر تخصصی ارسال شود.'),ActionStep(4,'snapshot','سیستم','ذخیره شواهد رخداد')],lifecycle='Validated'),
    ]
    return InspectionTemplate(key='tpl.sausage_batter_mixing',name_fa='کنترل صنعتی دیگ اختلاط سوسیس',version='4.1.0',process_stage='دیگ و اختلاط',lifecycle='Validated',description='Template تخصصی مرحله دوم؛ شاخص‌های محصول، حرکت، پوشش اختلاط، ناحیه مرده، Triggerهای چندشاهدی و اقدام اپراتوری.',metrics=metrics,triggers=triggers,actions=actions,product_weight=75,process_weight=25,ai_review_below=80)
