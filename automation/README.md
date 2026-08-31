# الأتمتة — محرك الاستخبارات وتوليد المحتوى والنشر

## كيف يعمل النظام

```
  المصادر (sources.yml)              profile/persona.yml + facts.yml
        │                                      │
        ▼                                      ▼
  news_engine.py --discover  ←─── الأوزان والعتبات وخريطة الاهتمامات
        │  جمع → استبعاد غير ذي الصلة → تجميع المكرر → مصداقية → ملاءمة → ثقة الحقائق
        ▼
  queue/news.jsonl  (قصص مرتّبة 0-100 + فرص أعمال مرصودة)
        │
        ▼
  generate_posts.py --from-news        (أو --week من بنك الأفكار)
        │  زاوية واحدة → طبقة رؤية يحيى → نسخة لكل منصة → فحص سلامة (أخضر/أصفر/أحمر)
        ▼
  queue/queue.csv  (status=draft)
        │
        ▼  مراجعتك: draft → approved  (أو rejected — وهي إشارة تعلّم)
        │
  publish.py  ← كل ساعة عبر GitHub Actions — ينشر المستحق فقط
        ▼
  X / LinkedIn / Instagram / TikTok / الموقع
        │
        ▼
  analytics/performance.csv → feedback.py --learn → learning/weights.yml
        └────────── يعيد ضبط ترتيب الأخبار القادمة (الأعمدة الناجحة ترتفع) ──────────┘
```

## الملفات

| الملف | الدور |
|---|---|
| `persona.py` | القلب: الترتيب، التجميع، ثقة الحقائق، مستويات الاعتماد، ذاكرة المحتوى، بناء تعليمات النموذج |
| `news_engine.py` | الاكتشاف والترتيب والتقرير الأسبوعي |
| `generate_posts.py` | تحويل الأخبار/الأفكار إلى مسودات موسومة بالكامل |
| `publish.py` | النشر المجدول ببوابة الاعتماد |
| `feedback.py` | التعلّم من الأداء ومن قرارات يحيى |
| `sources.yml` | مصادر الأخبار ودرجة مصداقية كل مصدر |
| `learning/weights.yml` | مضاعِفات الأعمدة — تُولَّد آلياً |

## التشغيل

```bash
pip install -r requirements.txt
cp config.example.yml config.yml     # وعبّئ المفاتيح — لا يُرفع إلى git أبداً

python persona.py --self-test                 # فحص منطق الترتيب والسلامة (بلا مفاتيح)
python news_engine.py --check-sources         # فحص روابط المصادر
python news_engine.py --discover              # دورة اكتشاف وترتيب (بلا مفاتيح كذلك)
python news_engine.py --top 10                # أهم القصص المخزّنة
python generate_posts.py --from-news          # مسودات من أهم الأخبار  (يحتاج مفتاح Anthropic)
python generate_posts.py --week               # أسبوع محتوى من بنك الأفكار
python publish.py --dry-run                   # ما الذي سيُنشر الآن؟
python news_engine.py --report                # تقرير الاستخبارات الأسبوعي
python feedback.py --learn                    # تحديث أوزان التعلّم
```

`news_engine.py` و`persona.py` يعملان بلا أي مفاتيح — التوليد وحده يحتاج مفتاح Anthropic.

## بوابة الاعتماد (§37 من المواصفة)

| المستوى | متى يُمنح | شرط النشر |
|---|---|---|
| **أخضر** | معلومة عامة موثّقة أو محتوى تعليمي، بلا رأي أو ادعاء شخصي | `approved`، أو آلياً فقط إذا `auto_publish_green: true` و`require_approval: false` |
| **أصفر** | رأي أو توقع أو تعليق تجاري، أو ثقة حقائق دون 0.8، أو تشابه مع منشور سابق | `approved` بشرياً |
| **أحمر** | مصطلحات مالية/قانونية/سياسية/شخصية، ادعاء تجربة غير موثّقة، ثقة حقائق دون 0.6 | `approved` بشري صريح — لا نشر آلي إطلاقاً |

## مفاتيح الـ API

| المنصة | المطلوب | ملاحظات |
|--------|---------|---------|
| توليد المحتوى | Anthropic API key | console.anthropic.com |
| X / تويتر | X API v2 (خطة Basic) | النشر الآلي عبر API الرسمي مسموح |
| لينكدإن | LinkedIn Marketing API | الرمز صالح 60 يوماً — جدّده |
| انستقرام | Meta Graph API + حساب Business | يتطلب ربطاً بصفحة فيسبوك ورابط صورة عام |
| تيك توك | Content Posting API | يتطلب موافقة تطبيق — حتى ذلك: صوّر يدوياً |

**بديل موحّد:** وجّه `publish.py` إلى Buffer / Typefully / Metricool — استبدل دوال `PUBLISHERS` فقط.

## حدود لا تُتجاوز

- لا تنشر أكثر من الإيقاع المحدد في الاستراتيجية — الإغراق يقتل الوصول.
- لا ردود آلية ولا متابعة/إلغاء متابعة آلية — مخالفة لشروط المنصات.
- كل رقم في المحتوى يجب أن يكون في المصدر أو في `facts.yml`؛ ما عداه يُحذف.
- السوشيال ميديا مصدر اكتشاف لا مصدر توثيق (§18).
