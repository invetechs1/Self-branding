# أدوات توليد المقاطع

المقاطع ليست تسجيل شاشة: تُبنى صفحة HTML من مشاهد معرَّفة في بايثون، ثم تُسجَّل
عبر متصفح بلا واجهة. الفائدة أن المحتوى قابل للتحديث — عدّل نصاً وأعد التوليد.

```
مشاهد (SCENES في build_*.py) → صفحة HTML → تسجيل Playwright → ترميز ffmpeg → mp4
```

## المتطلبات

```bash
pip install playwright imageio-ffmpeg
playwright install chromium
# أو استخدم متصفحاً مثبتاً لديك:  export CHROME_BIN=/path/to/chrome
```

## الاستخدام

```bash
# 1) ابنِ الصفحة
python docs/videos/tools/build_improvements.py        # ينتج improvements.html

# 2) راجع مشاهد بعينها قبل تسجيل ثلاث دقائق كاملة
python docs/videos/tools/shots.py docs/videos/tools/improvements.html 0 3 7

# 3) سجّل
python docs/videos/tools/record.py \
    docs/videos/tools/improvements.html docs/videos/06-seven-improvements.mp4
```

| الملف | ينتج |
|---|---|
| `build_walkthrough.py` | جولة في النظام — بنيته ومنطقه |
| `build_improvements.py` | التحسينات السبعة |
| `shots.py` | لقطات لمشاهد محددة (للمراجعة السريعة) |
| `record.py` | التسجيل والترميز |

## التعديل

كل بنّاء ملف مستقل بذاته: `SCENES` في أعلاه، والمحرّك أسفله. غيّر نص مشهد أو أضف
مشهداً إلى القائمة وأعد الخطوات الثلاث. المدة تُضبط بحقل `t` (بالثواني) لكل مشهد.

أنواع المشاهد المتاحة تختلف بين البنّائين (`title`, `grid`, `improve`, `gate`,
`before_after`, `table`, `weights`, `numbers`, `status`, `tree`, `pipeline`, `daily`, `end`)
— انظر دالة `render` في كل ملف.

## ملاحظات

- المقاس 1280×720 والخط DejaVu — يدعم العربية. لا صوت في المقاطع؛ النص كله على الشاشة.
- الصفحة تُعلم انتهاءها بـ `window.__done`، فالتسجيل يتوقف تلقائياً.
- لا تحتاج هذه الأدوات أي مفتاح API ولا اتصالاً بالمنصات.
