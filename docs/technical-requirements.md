# Technical Requirements Document (TRD)
## Yahya AI Persona & Content Intelligence Platform — v1.0

> ترجمة [`profile/persona-spec.md`](../profile/persona-spec.md) إلى نظام قابل للبرمجة مباشرة:
> جداول قاعدة البيانات، وكلاء الذكاء الاصطناعي، مصادر الأخبار، خوارزمية الترتيب، سير الاعتماد،
> لوحة التحكم، المجدول، تكامل LinkedIn/X/Instagram، ومحرك التعلّم من قبول يحيى ورفضه.
>
> **قبل هذا المستند:** [`docs/project-brief-EN.md`](project-brief-EN.md) يشرح للمطوّر *لماذا* نبني
> هذا النظام وما معيار نجاحه — اقرأه أولاً، فهو يفسّر القرارات التقنية هنا.
>
> **النموذج المرجعي العامل موجود في هذا المستودع** (`automation/`) — يمكن تشغيله اليوم كنسخة CLI،
> ويصلح كمواصفة تنفيذية للنسخة السحابية متعددة المستخدمين.

---

## 1. معمارية النظام

```
                       ┌──────────────────────────────────────────┐
   المصادر  ─────────► │ 1. Ingestion Service (RSS/API/Scrapers)   │
   RSS · APIs          └───────────────┬──────────────────────────┘
   بيانات رسمية                        ▼
                       ┌──────────────────────────────────────────┐
                       │ 2. Normalizer + Deduper (story clusters) │
                       └───────────────┬──────────────────────────┘
                                       ▼
                       ┌──────────────────────────────────────────┐
   persona.yml ──────► │ 3. Scoring Engine (relevance 0-100)      │
   learning weights    └───────────────┬──────────────────────────┘
                                       ▼
                       ┌──────────────────────────────────────────┐
                       │ 4. AI Agents (verify → angle → insight → │
   facts.yml ────────► │    platform drafts → safety review)      │
                       └───────────────┬──────────────────────────┘
                                       ▼
                       ┌──────────────────────────────────────────┐
                       │ 5. Approval Workflow (green/yellow/red)  │
                       └───────────────┬──────────────────────────┘
                                       ▼
                       ┌──────────────────────────────────────────┐
                       │ 6. Scheduler + Publishers (X/LI/IG)      │
                       └───────────────┬──────────────────────────┘
                                       ▼
                       ┌──────────────────────────────────────────┐
                       │ 7. Metrics Collector → 8. Learning Engine│
                       └──────────────────────────────────────────┘
                                       └──► يعيد ضبط أوزان (3)
```

**التقنيات المقترحة:** Python 3.12 (FastAPI) للخلفية · PostgreSQL 16 + `pgvector` · Redis (طابور
وذاكرة مؤقتة) · Celery/APScheduler للجدولة · Next.js للوحة التحكم · Claude API لوكلاء الذكاء الاصطناعي.
النسخة الحالية في `automation/` تستبدل PostgreSQL بـ CSV/JSONL و Celery بـ GitHub Actions — نفس المنطق.

---

## 2. جداول قاعدة البيانات

### 2.1 الشخصية والمعرفة

```sql
-- الشخصية والأوزان (نسخة قاعدة البيانات من profile/persona.yml)
CREATE TABLE persona_config (
  id              SERIAL PRIMARY KEY,
  version         TEXT NOT NULL,
  config          JSONB NOT NULL,          -- كامل persona.yml
  active          BOOLEAN DEFAULT TRUE,
  updated_at      TIMESTAMPTZ DEFAULT now()
);

-- قاعدة المعرفة الشخصية (§42) — كل ما يجوز الاستشهاد به في المحتوى
CREATE TABLE knowledge_items (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kind            TEXT NOT NULL,           -- bio|company|project|education|opinion|quote|goal|product
  title           TEXT NOT NULL,
  body            TEXT NOT NULL,
  is_public       BOOLEAN DEFAULT FALSE,   -- FALSE = لا يُستخدم في محتوى منشور
  confidence      NUMERIC(3,2) DEFAULT 1.0,
  source          TEXT,
  embedding       VECTOR(1024),            -- للاسترجاع الدلالي قبل الكتابة
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- خريطة الاهتمامات (§14) — قابلة للتعديل من اللوحة
CREATE TABLE interests (
  id              SERIAL PRIMARY KEY,
  name            TEXT UNIQUE NOT NULL,
  tier            SMALLINT NOT NULL CHECK (tier BETWEEN 1 AND 3),
  aliases         TEXT[] DEFAULT '{}',
  pillar          TEXT REFERENCES pillars(key),
  enabled         BOOLEAN DEFAULT TRUE
);

CREATE TABLE pillars (
  key             TEXT PRIMARY KEY,        -- ai_technology, construction_engineering, ...
  label_ar        TEXT NOT NULL,
  label_en        TEXT NOT NULL,
  target_share    NUMERIC(4,3) NOT NULL,   -- §26 المزيج المستهدف
  multiplier      NUMERIC(4,3) DEFAULT 1.0 -- يكتبه محرك التعلّم (§40)
);
```

### 2.2 الأخبار والاستخبارات

```sql
CREATE TABLE sources (
  id              SERIAL PRIMARY KEY,
  name            TEXT NOT NULL,
  url             TEXT NOT NULL,
  kind            TEXT NOT NULL,           -- rss|api|scrape|social
  source_type     TEXT NOT NULL,           -- official_government|official_company|... (§19)
  credibility     SMALLINT NOT NULL,       -- 0-100
  region          TEXT,
  enabled         BOOLEAN DEFAULT TRUE,
  last_fetched_at TIMESTAMPTZ,
  failure_count   SMALLINT DEFAULT 0       -- تعطيل تلقائي بعد فشل متكرر
);

CREATE TABLE stories (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id       INT REFERENCES sources(id),
  url             TEXT UNIQUE NOT NULL,
  title           TEXT NOT NULL,
  summary         TEXT,
  body            TEXT,
  language        TEXT DEFAULT 'en',
  published_at    TIMESTAMPTZ,
  fetched_at      TIMESTAMPTZ DEFAULT now(),
  embedding       VECTOR(1024),            -- لكشف التكرار الدلالي (§21)
  cluster_id      UUID REFERENCES story_clusters(id),
  scores          JSONB,                   -- كل المكوّنات السبعة + الإجمالي
  relevance       NUMERIC(4,1),            -- 0-100 (فهرس للترتيب)
  pillar          TEXT REFERENCES pillars(key),
  region          TEXT,
  entities        JSONB,                   -- شركات/أشخاص/أرقام مستخرجة
  opportunities   JSONB,                   -- §45
  status          TEXT DEFAULT 'new'       -- new|scored|clustered|used|ignored
);
CREATE INDEX ON stories (relevance DESC, published_at DESC);
CREATE INDEX ON stories USING hnsw (embedding vector_cosine_ops);

CREATE TABLE story_clusters (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  headline        TEXT NOT NULL,
  primary_story   UUID,
  source_count    SMALLINT DEFAULT 1,
  fact_confidence NUMERIC(3,2),            -- §22
  key_facts       JSONB,                   -- الحقائق المتفق عليها بين المصادر
  conflicts       JSONB,                   -- التعارضات المرصودة (تمنع النشر الآلي)
  first_seen_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE trends (                       -- §46
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pillar          TEXT REFERENCES pillars(key),
  headline        TEXT NOT NULL,
  story_ids       UUID[] NOT NULL,
  strength        NUMERIC(4,1),
  detected_at     TIMESTAMPTZ DEFAULT now()
);
```

### 2.3 المحتوى والاعتماد والنشر

```sql
CREATE TABLE ideas (                        -- §41 بنك الأفكار
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title           TEXT NOT NULL,
  pillar          TEXT REFERENCES pillars(key),
  angle           TEXT,
  source_story    UUID REFERENCES stories(id),
  status          TEXT DEFAULT 'new',      -- new|drafted|published|parked|rejected
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE posts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id      UUID REFERENCES story_clusters(id),
  idea_id         UUID REFERENCES ideas(id),
  platform        TEXT NOT NULL,           -- linkedin|x|x_thread|instagram|tiktok|article
  language        TEXT NOT NULL,           -- ar|en
  pillar          TEXT REFERENCES pillars(key),
  content_type    TEXT NOT NULL,           -- §27
  hook            TEXT,                    -- أول سطر — يُقاس أداؤه لاحقاً
  body            TEXT NOT NULL,
  media_brief     TEXT,
  approval_level  TEXT NOT NULL CHECK (approval_level IN ('green','yellow','red')),
  review_notes    TEXT,
  fact_confidence NUMERIC(3,2),
  relevance       NUMERIC(4,1),
  similarity_max  NUMERIC(4,3),            -- §43 أقصى تشابه مع منشور سابق
  status          TEXT DEFAULT 'draft',    -- draft|approved|rejected|scheduled|posted|failed
  scheduled_for   TIMESTAMPTZ,
  posted_at       TIMESTAMPTZ,
  external_id     TEXT,                    -- معرّف المنشور على المنصة
  embedding       VECTOR(1024),
  created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON posts (status, scheduled_for);

CREATE TABLE approvals (                    -- سجل قرارات يحيى = وقود التعلّم
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id         UUID REFERENCES posts(id) ON DELETE CASCADE,
  decision        TEXT NOT NULL,           -- approved|rejected|edited
  edit_diff       TEXT,                    -- ما غيّره يحيى بالضبط
  reason_tags     TEXT[],                  -- tone|inaccurate|off-brand|repetitive|sensitive|weak-insight
  decided_by      TEXT DEFAULT 'yahya',
  decided_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE post_metrics (                 -- §39
  id              BIGSERIAL PRIMARY KEY,
  post_id         UUID REFERENCES posts(id) ON DELETE CASCADE,
  captured_at     TIMESTAMPTZ DEFAULT now(),
  impressions     INT, views INT, likes INT, comments INT, shares INT, saves INT,
  profile_visits  INT, followers_gained INT, clicks INT,
  engagement_rate NUMERIC(6,4)
);

CREATE TABLE learning_weights (             -- §40 نسخ تاريخية لأوزان التعلّم
  id              BIGSERIAL PRIMARY KEY,
  computed_at     TIMESTAMPTZ DEFAULT now(),
  weights         JSONB NOT NULL,          -- {pillar: multiplier}
  sample_size     INT,
  notes           TEXT
);

CREATE TABLE audit_log (                    -- كل نشر/رفض/تعديل إعدادات
  id              BIGSERIAL PRIMARY KEY,
  actor           TEXT, action TEXT, entity TEXT, entity_id UUID,
  payload         JSONB, created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 3. وكلاء الذكاء الاصطناعي (AI Agents)

كل وكيل مهمة واحدة، مدخلات ومخرجات JSON صارمة (tool schema)، وقابل للاختبار منفرداً.

| # | الوكيل | المدخل | المخرج | النموذج المقترح |
|---|--------|--------|--------|------------------|
| 1 | **Relevance Agent** | قصة مطبّعة | مكوّنات الدرجة + العمود + المنطقة | خوارزمي أولاً؛ LLM صغير للحالات الملتبسة |
| 2 | **Dedup/Cluster Agent** | قصص + متجهات | معرّف العنقود + المصدر الأساسي | تشابه متجهي + LLM للحسم |
| 3 | **Fact Verification Agent** (§22) | عنقود + المصادر | `{claims[], agreed_facts[], conflicts[], confidence}` | Claude Sonnet |
| 4 | **Angle Agent** (§23) | عنقود + الشخصية | زاوية واحدة + سبب أهميتها ليحيى | Claude Sonnet |
| 5 | **Insight Agent** (§24) | عنقود + الزاوية + المعرفة المسترجعة | فقرة الرؤية + الأثر السعودي | Claude Opus |
| 6 | **Writer Agent** (§27-32) | الرؤية + دليل المنصة | نص المنشور + الخطّاف + وصف البصري | Claude Sonnet |
| 7 | **Safety Agent** (§33-37) | النص + الشخصية + قاعدة المعرفة | `{level, reasons[], edits[]}` | Claude Sonnet + قواعد حتمية |
| 8 | **Memory Agent** (§43) | النص + المنشورات السابقة | `{similarity_max, duplicate_of}` | تشابه متجهي |
| 9 | **Opportunity Agent** (§45) | عنقود | فرص: ميزة بصير / شراكة / استثمار / تنافسية | Claude Sonnet |
| 10 | **Trend Agent** (§46) | عناقيد الأسبوع | اتجاهات + مقترح تعمّق | Claude Opus |
| 11 | **Report Agent** (§47) | كل ما سبق | التقرير الأسبوعي | Claude Sonnet |

**قواعد إلزامية على كل وكيل كاتب:**
1. لا يستقبل الحقائق الشخصية إلا عبر `knowledge_items.is_public = TRUE`.
2. يمنع تجاوز حارس السلامة: مخرَج الوكيل 7 نهائي ولا يُعدَّل برمجياً لرفع المستوى.
3. أي رقم في النص يجب أن يُطابق `story_clusters.key_facts` وإلا يُحذف تلقائياً ويُسجَّل في `review_notes`.

---

## 4. خوارزمية الترتيب (Scoring Algorithm)

```
relevance = ( 25·personal_interest + 20·business_relevance + 15·saudi_gcc
            + 15·strategic_importance + 10·audience_value + 10·freshness
            +  5·source_credibility ) × leadership_boost × learning_multiplier
```

| المكوّن | الحساب |
|---|---|
| `personal_interest` | مطابقة خريطة الاهتمامات مع المرادفات؛ Tier1=1.0 · Tier2=0.7 · Tier3=0.4، تشبّع عند 3 مطابقات |
| `business_relevance` | مطابقة مجالات أعمال يحيى؛ +0.15 لكل مجال إضافي متقاطع |
| `saudi_gcc` | أعلى وزن جغرافي مطابق (السعودية 1.0 ← عالمي 0.4)، وقائمة المتابعة السعودية ترفعه إلى 1.0 |
| `strategic_importance` | إشارات (استحواذ/تمويل/تنظيم/إلزام/شراكة/طرح) عالية، و(تقرير/دراسة/توسّع) متوسطة |
| `audience_value` | إشارات القيمة العملية (تكلفة، إنتاجية، عائد، دراسة حالة، أثر) |
| `freshness` | `0.5^(age_hours / 24)`، صفر بعد 168 ساعة |
| `source_credibility` | `sources.credibility / 100` |
| `leadership_boost` | 1.25 لتقاطع AI×Construction×Business، 1.15 للتقاطعات الثانوية (§44) |
| `learning_multiplier` | `pillars.multiplier` من محرك التعلّم، محصور بين 0.7 و1.4 |

**العتبات:** دخول خط الإنتاج ≥ 55 · موضوع تعمّق ≥ 78 · تشابه التكرار ≥ 0.55 · مصداقية الادعاءات الرقمية ≥ 80.

**التنفيذ المرجعي:** `automation/persona.py::score_story` — واختباره `python automation/persona.py --self-test`.

**كشف التكرار (§21):** في الإنتاج استخدم `pgvector` (تشابه جيبي ≥ 0.86 خلال 72 ساعة) مع
احتياطي معجمي `0.5·Jaccard + 0.5·Overlap` بعد إزالة كلمات الوقف والجذر الخفيف — المطبّق حالياً في
`persona.py::similarity`.

**ثقة الحقائق (§22):** `0.85·أعلى_مصداقية + 0.1·(مصادر_مستقلة − 1) − 0.15·تعارض_أرقام`
→ أقل من 0.6 = أحمر، ومن 0.6 إلى 0.8 = أصفر، وفوقها = مؤهَّل للأخضر.

---

## 5. مصادر الأخبار (News APIs)

| الطبقة | المصدر | الاستخدام | التكلفة |
|---|---|---|---|
| أساسي | RSS مباشر (`automation/sources.yml`) | 17 مصدراً جاهزاً: سعودية، خليجية، ConTech، AI، عقار | مجاني |
| توسّعي | NewsAPI.org / GNews / Bing News API | تغطية كلمات مفتاحية أوسع (§49) | 50–500$ شهرياً |
| مفتوح | GDELT 2.0 | رصد عالمي واسع + تحليل نبرة | مجاني |
| رسمي | واس · رؤية 2030 · PIF · هيئة المقاولين · سكني | لا RSS — كشط مجدول أو متابعة يدوية | مجاني |
| مالي | تداول السعودية · أرقام · Zawya | إعلانات الشركات المدرجة | متفاوت |
| مبكّر | X API (قوائم منتقاة) | اكتشاف مبكر فقط — **لا يُعد مصدراً موثقاً (§18)** | خطة Basic |

**قواعد الجلب:** احترام `robots.txt` وحدود المعدل · مهلة 15 ثانية لكل مصدر · فشل مصدر لا يوقف الدورة ·
تعطيل تلقائي بعد 5 إخفاقات متتالية · تخزين النص الخام مرة واحدة (`stories.body`) لتفادي إعادة الجلب.

---

## 6. سير الاعتماد (Approval Workflow)

```
draft ──(Safety Agent)──► green ──┬─(auto_publish_green=true)─► scheduled ──► posted
                                  └─(الافتراضي)──────────────► pending_review
       ─────────────────► yellow ──────────────────────────► pending_review
       ─────────────────► red ────────────────────────────► manual_only
pending_review ──(يحيى: اعتماد)──► scheduled
               ──(يحيى: تعديل)───► scheduled + حفظ الفرق في approvals.edit_diff
               ──(يحيى: رفض)────► rejected + reason_tags  ──► محرك التعلّم
```

**قواعد صارمة:**
- الأحمر لا يُنشر آلياً في أي حال؛ يتطلب قراراً بشرياً صريحاً مسجلاً في `approvals`.
- `auto_publish_green` يبقى `false` في أول 3 أشهر (الصوت الشخصي هو المنتج).
- كل تعديل بشري يُخزَّن كفرق نصي — وهو أثمن إشارة تدريب في النظام.
- أي منشور يحمل رقماً غير موجود في `key_facts` يُخفَّض تلقائياً إلى أحمر.

**التنفيذ المرجعي:** `automation/persona.py::classify_approval` و`automation/publish.py::publishable`.

---

## 7. المجدول (Scheduler)

| المهمة | التكرار | الأمر المرجعي |
|---|---|---|
| جلب وترتيب الأخبار | كل 3 ساعات | `news_engine.py --discover` |
| توليد مسودات من الأخبار | يومياً 06:00 (الرياض) | `generate_posts.py --from-news` |
| توليد أسبوع من بنك الأفكار | الأحد 05:00 | `generate_posts.py --week` |
| النشر المستحق | كل ساعة | `publish.py` |
| جمع مقاييس الأداء | كل 6 ساعات (وبعد 1/24/72 ساعة من كل نشر) | `metrics_collector` |
| محرك التعلّم | الجمعة 22:00 | `feedback.py --learn` |
| التقرير الأسبوعي | السبت 08:00 | `news_engine.py --report` |
| فحص صلاحية المصادر | أسبوعياً | `news_engine.py --check-sources` |

**التوقيت:** كل الجدولة بتوقيت `Asia/Riyadh`. نوافذ النشر المفضّلة تُشتق من `analytics/learning-report.md`
(أفضل الأوقات المقاسة فعلياً) لا من افتراضات عامة.

---

## 8. تكامل المنصات

### 8.1 X (تويتر)
- X API v2، خطة Basic فأعلى، OAuth 1.0a user context للنشر.
- `POST /2/tweets`؛ الثريد بربط `in_reply_to_tweet_id` تسلسلياً (منفّذ في `publish.py::post_twitter`).
- الحدود: 280 حرفاً/تغريدة · احترام حدود المعدل مع إعادة محاولة أسّية · لا ردود آلية ولا متابعة آلية.

### 8.2 LinkedIn
- OAuth 2.0 (`w_member_social`)، النشر عبر `POST /v2/ugcPosts` بـ `person_urn`.
- الرمز صالح 60 يوماً → تخزين `refresh_token` وتجديد تلقائي قبل 7 أيام من الانتهاء.
- الصور: تسجيل الوسيط (`registerUpload`) ثم الرفع ثم الإشارة إليه في المنشور.

### 8.3 Instagram
- Meta Graph API + حساب Business مربوط بصفحة فيسبوك.
- نشر من خطوتين: `POST /{ig-user-id}/media` (حاويات الكاروسيل) ثم `media_publish`.
- الصور يجب أن تكون على رابط عام (S3/CDN) — ولّدها من نص الشرائح عبر قالب تصميم موحّد.

### 8.4 TikTok
- Content Posting API — يتطلب مراجعة تطبيق. حتى ذلك: النظام يخرج السكربت وتُصوَّر يدوياً.

### 8.5 بديل موحّد
Buffer / Typefully / Metricool API — يستبدل طبقة النشر كاملة بنقطة تكامل واحدة.
الكود مقسّم بحيث تُستبدل دوال `PUBLISHERS` فقط.

---

## 9. لوحة التحكم (§48)

**شاشة 1 — استخبارات اليوم:** أهم القصص بالدرجة ومكوّناتها · اتجاهات مرصودة · تبويبات
(سعودي / ذكاء اصطناعي / إنشاءات / عقار / أعمال) · بطاقة كل قصة تعرض المصادر وثقة الحقائق والفرص.

**شاشة 2 — فرص المحتوى:** لكل عنقود أزرار: `انشر الآن` · `اكتب تحليلاً` · `احفظ لاحقاً` · `تجاهل`
(كل ضغطة إشارة تدريب تُسجَّل في `approvals`/`ideas`).

**شاشة 3 — محتوى يحيى:** مسودات (بوسم أخضر/أصفر/أحمر وأسباب المراجعة) · محرر جانبي مع فرق النص ·
مجدول · منشور + الأداء.

**شاشة 4 — الأداء والتعلّم:** تفاعل حسب العمود/المنصة/اللغة/الوقت/الخطّاف · أوزان التعلّم الحالية
وسبب كل وزن · نسبة الاعتماد مقابل الرفض وأسباب الرفض.

**شاشة 5 — الإعدادات:** خريطة الاهتمامات · المصادر ومصداقيتها · العتبات والأوزان · مزيج الأعمدة ·
قواعد السلامة · مفاتيح المنصات.

---

## 10. محرك التعلّم من قبول يحيى ورفضه (§39-40)

**إشارتان لكل عمود محتوى:**
1. **أداء الجمهور** — تفاعل مرجّح: `(likes + 2·comments + 3·shares + 2·saves + 1.5·profile_visits + 4·followers)/impressions`
2. **تفضيل يحيى** — نسبة الاعتماد إلى إجمالي ما عُرض عليه من هذا العمود.

```
multiplier(pillar) = clamp( 1 + 0.7·(perf_ratio − 1) + 0.3·(approval_ratio − 1), 0.7, 1.4 )
```
بشرط 3 عيّنات على الأقل، وإلا يبقى الوزن محايداً (1.0). يدخل المضاعِف مباشرة في خوارزمية الترتيب (§4).

**إشارات أدق يجب تخزينها منذ اليوم الأول** (حتى قبل استخدامها):
- `approvals.reason_tags` — لماذا رُفض: نبرة، عدم دقة، خارج العلامة، تكرار، حساسية، رؤية ضعيفة.
- `approvals.edit_diff` — تعديلات يحيى النصية: أثمن مصدر لضبط الصوت لاحقاً (few-shot أو تدريب لاحق).
- أداء الخطّافات (`posts.hook`) وأطوال النصوص واللغة وأوقات النشر.

**الحماية من الانهيار في تخصص واحد:** حدّ أدنى 5% لكل عمود في المزيج مهما انخفض وزنه، وسقف 1.4
للمضاعِف — التعلّم يضبط الأولوية ولا يلغي التنوع.

**التنفيذ المرجعي:** `automation/feedback.py` → `automation/learning/weights.yml` + `analytics/learning-report.md`.

---

## 11. الأمن والامتثال

- المفاتيح في مدير أسرار (AWS Secrets Manager / GitHub Secrets) — لا في المستودع (`config.yml` مستبعد).
- تشفير `knowledge_items` غير العامة في حالة السكون، وصلاحية قراءة مقيدة بالوكلاء الكتابيين.
- تدقيق كامل (`audit_log`) لكل نشر وكل تغيير إعدادات.
- احترام شروط كل منصة: لا ردود آلية، لا متابعة/إلغاء متابعة آلي، لا كشط لما تمنعه المنصة.
- الاحتفاظ بالنص الخام للمصادر ضمن حدود الاستخدام العادل — النشر يكون بمحتوى أصلي دائماً (§33).

---

## 12. معايير القبول (Acceptance Criteria)

1. دورة اكتشاف واحدة تجلب ≥ 100 خبر من ≥ 10 مصادر، وتُخرج ≤ 20 قصة فوق العتبة، مجمّعة في عناقيد بلا تكرار ظاهر.
2. كل منشور مولّد يحمل: عموداً، نوع محتوى، لغة، مستوى اعتماد مع أسبابه، درجة ملاءمة، ورابط مصدر.
3. لا يظهر في أي منشور رقم أو ادعاء شخصي غير موجود في المصادر أو في قاعدة المعرفة — يُختبر بعيّنة 50 منشوراً.
4. لا يُنشر منشور أحمر آلياً في أي سيناريو اختبار.
5. تكرار الحجة أو الخطّاف مع منشور سابق يُرصد قبل النشر (§43).
6. التقرير الأسبوعي يُولَّد آلياً ويحوي البنود الثمانية (§47).
7. بعد 30 منشوراً مقيساً، تتغير أوزان الأعمدة فعلياً وينعكس التغيير في ترتيب الأخبار.
8. المزيج الفعلي المنشور خلال 8 أسابيع لا ينحرف عن المستهدف (§26) بأكثر من ±7 نقاط مئوية لكل عمود.

---

## 13. خطة التنفيذ المرحلية

| المرحلة | المدة | المخرج |
|---|---|---|
| **1. الأساس** | أسبوعان | جداول القاعدة + الجلب + الترتيب + كشف التكرار (المنطق جاهز في `automation/`) |
| **2. الوكلاء** | أسبوعان | التحقق، الزاوية، الرؤية، الكاتب، السلامة + قاعدة المعرفة والاسترجاع |
| **3. اللوحة والاعتماد** | 3 أسابيع | الشاشات الخمس + سير الاعتماد + تسجيل قرارات يحيى |
| **4. النشر والتكامل** | أسبوعان | X + LinkedIn + Instagram + المجدول + إعادة المحاولة |
| **5. القياس والتعلّم** | أسبوعان | جامع المقاييس + محرك التعلّم + التقرير الأسبوعي |
| **6. الاستخبارات** | أسبوعان | الاتجاهات، الفرص، رادار المنافسين، لوحة الأعمال |

**قاعدة الإطلاق:** لا تُفعَّل أي أتمتة نشر قبل مرور 3 أشهر من المراجعة البشرية الكاملة —
الصوت الشخصي هو المنتج، والأتمتة أداة لا بديل.
