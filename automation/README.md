# الأتمتة — توليد المحتوى والنشر المجدول

## كيف يعمل النظام

```
profile/facts.yml + content/idea-bank.md
        │
        ▼
generate_posts.py  ← يولّد أسبوع محتوى (Claude API) بكل الصيغ لكل المنصات
        │
        ▼
queue/queue.csv    ← طابور النشر (status=draft)
        │
        ▼  (مراجعتك البشرية: draft → approved)
        │
publish.py         ← يُشغَّل بجدولة (GitHub Actions كل ساعة)
        │            ينشر ما حان وقته عبر الـ APIs الرسمية
        ▼
X / Instagram / TikTok / LinkedIn
```

**المراجعة البشرية شرط:** `publish.py` لا ينشر إلا الصفوف بحالة `approved`. راجع المسودات، عدّلها بصوتك، ثم اعتمدها.

## المتطلبات

```bash
pip install -r requirements.txt
cp config.example.yml config.yml   # وعبّئ المفاتيح — لا ترفع config.yml إلى git أبداً
```

## مفاتيح الـ API المطلوبة (كلها رسمية ومتوافقة مع شروط المنصات)

| المنصة | المطلوب | ملاحظات |
|--------|---------|---------|
| توليد المحتوى | Anthropic API key | console.anthropic.com |
| X / تويتر | X API v2 (خطة Basic) | developer.x.com — النشر الآلي عبر API الرسمي مسموح |
| انستقرام | Meta Graph API + حساب Business | يتطلب ربط الحساب بصفحة فيسبوك |
| تيك توك | TikTok Content Posting API | يتطلب موافقة تطبيق مطور |
| لينكدإن | LinkedIn Marketing API | أو انشر يدوياً — منشوران أسبوعياً فقط |

**بديل أسرع للانطلاق:** إن لم ترغب بإدارة الـ APIs بنفسك، وجّه `publish.py` لمنصة جدولة
(Buffer / Typefully / Metricool) عبر الـ API الخاص بها — الكود مقسّم بحيث تستبدل طبقة النشر فقط.

## الاستخدام

```bash
# توليد محتوى الأسبوع القادم (مسودات)
python generate_posts.py --week

# مراجعة: افتح queue/queue.csv وغيّر status إلى approved لما يعجبك

# النشر (يُشغّل تلقائياً عبر GitHub Actions، أو يدوياً):
python publish.py
```

## حدود مهمة (لا تتجاوزها)

- لا تنشر أكثر من الإيقاع المحدد في الاستراتيجية — الإغراق يقتل الوصول.
- لا ردود آلية ولا متابعة/إلغاء متابعة آلية — مخالفة لشروط المنصات وتحرق الحساب.
- الأرقام والإنجازات في المحتوى المولّد تأتي حصراً من `facts.yml` — إن ولّد النموذج رقماً غير موجود فيه، احذفه.
