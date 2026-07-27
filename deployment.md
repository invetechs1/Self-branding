# دليل النشر عبر Docker

هذا المشروع يحتوي على جزأين قابلين للتشغيل بصورة Docker منفصلة:

| الصورة | المصدر | الوظيفة |
|--------|--------|---------|
| `self-branding-site` | [Dockerfile.site](Dockerfile.site) | يشغّل الموقع الشخصي الثابت (`site/`) عبر nginx |
| `self-branding-automation` | [Dockerfile.automation](Dockerfile.automation) | يشغّل سكربتات توليد ونشر المحتوى (`automation/generate_posts.py`, `automation/publish.py`) |

> **ملاحظة:** صورة `automation` تحتاج `automation/config.yml` (مفاتيح الـ API) لتنفيذ أي عملية توليد/نشر
> فعلية. هذا الملف مستثنى من git ومن الصورة (`.dockerignore`) لأنه يحوي أسراراً — مرره وقت التشغيل
> كـ volume، لا وقت البناء. بدون هذا الملف، السكربت يخرج برسالة خطأ واضحة (سلوك متوقع وآمن).

## المتطلبات

- Docker Engine 24+ (أو Docker Desktop على Windows/Mac).
- تنفيذ الأوامر التالية من جذر المستودع.

---

## 1. حذف الصورة الحالية (إن وُجدت)

قبل أي إعادة بناء، احذف الصورة القديمة لتفادي بقايا طبقات (layers) قديمة تحت نفس الاسم:

```bash
# صورة الموقع
docker rmi -f self-branding-site:latest

# صورة الأتمتة
docker rmi -f self-branding-automation:latest
```

`-f` يتجاهل الخطأ إن كانت الصورة غير موجودة أصلاً — آمن لتشغيله في أول مرة.

> إن كانت الصورة مستخدَمة من حاوية قائمة، أوقفها وأزلها أولاً:
> `docker rm -f self-branding-site-test` (أو اسم الحاوية لديك).

## 2. بناء الصورة الجديدة

```bash
# صورة الموقع (nginx يخدم site/)
docker build -f Dockerfile.site -t self-branding-site:latest .

# صورة الأتمتة (Python + generate_posts.py / publish.py)
docker build -f Dockerfile.automation -t self-branding-automation:latest .
```

## 3. التحقق من التشغيل

```bash
# الموقع — يفتح على http://localhost:8080
docker run -d --name self-branding-site -p 8080:80 self-branding-site:latest
curl http://localhost:8080/

# الأتمتة — تشغيل تجريبي بدون نشر فعلي (dry-run)، لا يحتاج مفاتيح API
docker run --rm self-branding-automation:latest automation/publish.py --dry-run

# لتشغيل التوليد الفعلي، مرر config.yml الحقيقي كـ volume:
docker run --rm -v "$(pwd)/automation/config.yml:/app/automation/config.yml:ro" \
  self-branding-automation:latest automation/generate_posts.py --week
```

بديل أبسط عبر Compose (يبني الصورتين ويشغّل الموقع):

```bash
docker compose up --build -d site
```

## 4. تحويل الصورة إلى ملف tar

بعد التأكد من عمل الصورة، صدّرها كملف tar (للنقل بلا Docker Hub، أو للأرشفة/النسخ الاحتياطي):

```bash
# صورة الموقع
docker save -o self-branding-site.tar self-branding-site:latest

# صورة الأتمتة
docker save -o self-branding-automation.tar self-branding-automation:latest
```

للتحقق من حجم الملفات الناتجة:

```bash
ls -lh self-branding-site.tar self-branding-automation.tar
```

### استيراد الصورة من ملف tar (على خادم آخر مثلاً)

```bash
docker load -i self-branding-site.tar
docker load -i self-branding-automation.tar
```

---

## تسلسل كامل جاهز للنسخ (الموقع كمثال)

```bash
docker rmi -f self-branding-site:latest
docker build -f Dockerfile.site -t self-branding-site:latest .
docker save -o self-branding-site.tar self-branding-site:latest
```

## ملاحظات أمنية

- لا تُدرج `automation/config.yml` (المفاتيح) داخل أي صورة أو ملف tar — هو مستثنى فعلاً عبر
  [.dockerignore](.dockerignore) و [.gitignore](.gitignore). تحقق دائماً قبل رفع أي `.tar` لمكان مشترك.
- ملفات `.tar` الناتجة كبيرة نسبياً وتحتوي كامل طبقات الصورة — لا ترفعها إلى git.
