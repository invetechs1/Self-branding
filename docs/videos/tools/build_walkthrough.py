#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني صفحة «جولة في النظام» — 12 مشهداً تشرح بنية النظام ومنطقه.

    python docs/videos/tools/build_walkthrough.py        # ينتج walkthrough.html
    python docs/videos/tools/shots.py walkthrough.html 0 3 7
    python docs/videos/tools/record.py walkthrough.html 05-system-walkthrough.mp4

عدّل SCENES أدناه ثم أعد البناء والتسجيل. لا تحتاج أي مفاتيح.
"""

import html, json
from pathlib import Path

HERE = Path(__file__).resolve().parent

SCENES = [
# ── 1 ──
dict(kind="title", t=12,
     eyebrow="ما بنيناه ولماذا",
     title="محرّك العلامة الشخصية",
     sub="يحيى حسين آل سلامه — مهندس ورائد أعمال",
     quote="النظام لا يسأل: «ماذا ننشر اليوم؟»<br>بل: «ماذا حدث في العالم اليوم ويجب أن يفهمه يحيى، "
           "وما الزاوية التي يمكنه إضافتها، وكيف تبني هذه الرؤية سمعته وفرص أعماله؟»"),
# ── 2 ──
dict(kind="bullets", t=16, num="01", head="المشكلة التي يحلها",
     intro="ثلاثة إخفاقات محددة — لا «قلة محتوى»:",
     items=[("⏱", "الإشارة مدفونة", "٢٠٠ خبر يومياً، خمسة تهمّك. فرزها يدوياً = ٩٠ دقيقة كل يوم. لا أحد يداوم على ذلك."),
            ("💭", "الرؤية تموت قبل أن تُكتب", "ردّ فعلك على الخبر هو المنتج. يُفكَّر فيه في السيارة ويُنسى بالمساء."),
            ("🚫", "المحتوى العام أسوأ من الصمت", "منشور يكتبه ذكاء اصطناعي بلا رأيك يُقرأ كفراغ — ويضرّ السمعة التي نبنيها.")]),
# ── 3 ──
dict(kind="position", t=13, num="02", head="التموضع الذي يحكم كل شيء",
     words=["الهندسة", "الأعمال", "التقنية", "الذكاء الاصطناعي", "العقار"],
     line="رائد أعمال يعرف الصناعات التقليدية من الداخل، ويبني التقنية التي تحوّلها.",
     note="ليس «مقاولاً» فقط، ولا «مؤسس شركة تقنية» فقط — القيمة في التقاطع."),
# ── 4 ──
dict(kind="tree", t=19, num="03", head="خريطة المستودع",
     rows=[("profile/", "الهوية: ملف الحقائق + الشخصية الرقمية التي يقرؤها الكود", "core"),
           ("automation/", "المحرّك: اكتشاف ← ترتيب ← توليد ← نشر ← تعلّم", "core"),
           ("strategy/", "الاستراتيجية، خارطة ١٢ شهراً، خطة SEO، أدلة المنصات", ""),
           ("content/", "بنك الأفكار، القوالب، المسودات الجاهزة للنشر", ""),
           ("analytics/", "قياس الأداء + تقارير الاستخبارات الأسبوعية", ""),
           ("docs/", "موجز المشروع ومستند المتطلبات التقنية للمطوّر", ""),
           ("outreach/", "عدة العلاقات الإعلامية والبودكاست", ""),
           ("site/", "الموقع الشخصي المحسّن لمحركات البحث", ""),
           (".github/", "ثلاثة مسارات آلية: نشر، استخبارات، اختبارات", "")]),
# ── 5 ──
dict(kind="pipeline", t=18, num="04", head="المسار: من خبر إلى منشور",
     steps=[("اكتشاف", "جمع متواصل من مصادر مصنّفة بالمصداقية", "١"),
            ("حكم", "درجة ملاءمة ٠-١٠٠ · تجميع الروايات المكررة · التحقق من الحقائق", "٢"),
            ("تفكير", "زاوية واحدة + طبقة رؤيتك + نسخة لكل منصة", "٣"),
            ("بوابة وتعلّم", "تصنيف سلامة ← مراجعتك ← نشر ← قياس ← إعادة ضبط", "٤")]),
# ── 6 ──
dict(kind="weights", t=16, num="05", head="لماذا يصعد خبر ويسقط آخر",
     bars=[("تطابق اهتماماتك", 25), ("صلته بأعمالك", 20), ("بُعده السعودي/الخليجي", 15),
           ("أهميته الاستراتيجية", 15), ("قيمته لجمهورك", 10), ("حداثته", 10), ("مصداقية مصدره", 5)],
     foot="ثم تُضرب النتيجة في دفعة تقاطع «ذكاء اصطناعي × إنشاءات × أعمال» (١.٢٥×) وفي ما تعلّمه النظام من أدائك."),
# ── 7 ──
dict(kind="files", t=17, num="06", head="ملفان يحكمان المحتوى كله",
     cards=[("profile/facts.yml", "مصدر الحقيقة الوحيد",
             "كل رقم وإنجاز وقصة شخصية تُؤخذ من هنا حصراً.<br>ما ليس فيه — لا يُكتب. هكذا يستحيل اختلاق تجربة.",
             ["identity: يحيى حسين آل سلامه", "ventures: عزوم · العراب · بصير", "products: BEVIP · AI CFO · ERP",
              "content_rules: لا أرقام إيرادات إطلاقاً"]),
            ("profile/persona.yml", "لوحة التحكم",
             "الاهتمامات والأوزان والعتبات وأدلة المنصات وقواعد السلامة.<br>تعدّلها بلا لمس سطر برمجي واحد.",
             ["interest_graph: ثلاث طبقات", "thresholds: عتبة الدخول ٥٥", "content_pillars: ثمانية أعمدة",
              "safety: ما لا يُنشر أبداً"])]),
# ── 8 ──
dict(kind="gate", t=16, num="07", head="بوابة الاعتماد — جوهر النظام",
     rows=[("green", "أخضر", "معلومة موثّقة أو محتوى تعليمي، بلا رأي أو ادعاء شخصي",
            "يُنشر بعد اعتمادك (أو آلياً إن فعّلت ذلك صراحةً)"),
           ("yellow", "أصفر", "رأي أو توقع، أو ثقة حقائق دون ٠.٨، أو تشابه مع منشور سابق",
            "مراجعة بشرية إلزامية"),
           ("red", "أحمر", "مالي · قانوني · سياسي · شخصي · ادعاء غير موثّق",
            "لا نشر آلي في أي إعداد مهما كان")],
     foot="المراجعة ليست احتكاكاً نتخلص منه — هي الميزة. صوتك هو المنتج."),
# ── 9 ──
dict(kind="learning", t=15, num="08", head="النظام يتعلّم منك ومن جمهورك",
     before=[("الإنشاءات والهندسة", 1.0), ("الاقتصاد السعودي", 1.0), ("الذكاء الاصطناعي", 1.0), ("التطوير العقاري", 1.0)],
     after=[("الإنشاءات والهندسة", 1.40), ("الاقتصاد السعودي", 1.03), ("الذكاء الاصطناعي", 0.85), ("التطوير العقاري", 0.70)],
     foot="إشارتان: تفاعل الجمهور + ما تعتمده وما ترفضه. والنتيجة تعيد ترتيب أخبار الغد — بحدود تمنع انهيار التنوع."),
# ── 10 ──
dict(kind="daily", t=16, num="09", head="يومك مع النظام: خمس دقائق",
     cmds=[("python automation/news_engine.py --discover", "يجمع ويرتّب ويجمّع المكرر — بلا تدخل منك"),
           ("python automation/generate_posts.py --from-news", "يحوّل أهم القصص إلى مسودات موسومة"),
           ("# راجع queue.csv: approved أو rejected", "دقائقك الخمس — والرفض نفسه يعلّم النظام"),
           ("python automation/publish.py", "ينشر المعتمد في موعده عبر الواجهات الرسمية")]),
# ── 11 ──
dict(kind="status", t=18, num="10", head="أين نحن الآن",
     done=["٧٣ فحصاً آلياً تمر كلها، وتعمل عند كل دفع إلى GitHub",
           "مسار كامل مُختبر: جلب RSS حقيقي ← ترتيب ← توليد ← نشر",
           "النشر إلى X ولينكدإن مُثبت ببنية الواجهتين الرسمية (ثريد مترابط صحيح)",
           "موجز المشروع ومستند المتطلبات التقنية جاهزان للمطوّر",
           "أول منشور جاهز للنشر في content/drafts/"],
     todo=[("عبّئ TODO في facts.yml", "سنوات الخبرة، مشروع واحد بالأرقام، إخفاق ودرسه — أعلى مُدخل أثراً"),
           ("مفاتيح X ولينكدإن", "حتى ذلك: النظام يولّد وأنت تنشر يدوياً"),
           ("تحقق من روابط المصادر", "python automation/news_engine.py --check-sources")]),
# ── 12 ──
dict(kind="end", t=12,
     title="الخلاصة",
     lines=["النظام يحوّل ٩٠ دقيقة فرز يومي إلى خمس دقائق مراجعة — دون أن يفقد ما يجعل المحتوى يستحق القراءة: أن رأيك فيه.",
            "الهدف ليس عدد المتابعين، بل: سمعة ← سلطة معرفية ← شبكة ← فرص أعمال."],
     repo="github.com/invetechs1/Self-branding"),
]


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1280px;height:720px;overflow:hidden;background:#0a0f1c;color:#e2e8f0;
  font-family:"DejaVu Sans",sans-serif;direction:rtl}
.scene{position:absolute;inset:0;padding:46px 62px 58px;opacity:0;transform:translateY(14px);
  transition:opacity .55s ease,transform .55s ease;display:flex;flex-direction:column;
  justify-content:center}
.scene.on{opacity:1;transform:none}
.rise{opacity:0;transform:translateY(12px);transition:opacity .5s ease,transform .5s ease}
.rise.in{opacity:1;transform:none}
.num{color:#2dd4bf;font-size:13px;letter-spacing:3px;margin-bottom:7px;font-weight:bold}
h1{font-size:40px;line-height:1.25;font-weight:bold;letter-spacing:-.5px}
h2{font-size:31px;line-height:1.3;font-weight:bold;margin-bottom:26px;letter-spacing:-.4px}
.accent{color:#2dd4bf}
.muted{color:#94a3b8}
.foot{margin-top:28px;padding-top:16px;color:#94a3b8;font-size:15px;line-height:1.6;
  border-top:1px solid #1e293b}
.progress{position:absolute;left:0;right:0;bottom:0;height:4px;background:#111b2e}
.progress>i{display:block;height:100%;background:linear-gradient(90deg,#2dd4bf,#0ea5e9);width:0}
.chip{position:absolute;left:62px;top:46px;color:#475569;font-size:12.5px;letter-spacing:1px}
#s0 .chip,#s11 .chip{display:none}
/* title */
.eyebrow{color:#2dd4bf;font-size:16px;letter-spacing:5px;margin-bottom:20px}
.sub{color:#94a3b8;font-size:20px;margin-top:14px}
.quote{margin-top:46px;border-right:3px solid #2dd4bf;padding:20px 24px;background:#0f1a2e;
  border-radius:0 10px 10px 0;font-size:20px;line-height:1.8;color:#cbd5e1;max-width:1000px}
/* bullets */
.bul{display:flex;gap:20px;align-items:flex-start;margin-bottom:24px;background:#0f1a2e;
  padding:20px 24px;border-radius:12px;border:1px solid #1e293b}
.bul .ico{font-size:26px;flex:0 0 auto;width:42px;text-align:center}
.bul b{display:block;font-size:21px;margin-bottom:7px}
.bul p{color:#94a3b8;font-size:16.5px;line-height:1.65}
.intro{color:#cbd5e1;font-size:18px;margin-bottom:26px}
/* position */
.words{display:flex;gap:16px;justify-content:center;align-items:center;margin:44px 0;flex-wrap:wrap}
.word{background:#0f1a2e;border:1px solid #1e4c49;color:#5eead4;padding:16px 26px;
  border-radius:12px;font-size:24px;font-weight:bold}
.x{color:#475569;font-size:22px}
.posline{text-align:center;font-size:25px;line-height:1.6;max-width:940px;margin:0 auto}
/* tree */
.row{display:flex;gap:18px;align-items:baseline;padding:10px 16px;border-radius:8px;margin-bottom:5px}
.row.core{background:#0f1a2e;border:1px solid #1e4c49}
.row code{font-family:"DejaVu Sans Mono",monospace;color:#5eead4;font-size:16.5px;
  width:150px;flex:0 0 auto;direction:ltr;text-align:right}
.row span{color:#94a3b8;font-size:16px}
.row.core span{color:#cbd5e1}
/* pipeline */
.pipe{display:flex;gap:14px;margin-top:12px}
.pstep{flex:1;background:#0f1a2e;border:1px solid #1e293b;border-radius:14px;padding:24px 20px;
  position:relative}
.pstep .pn{position:absolute;top:-15px;right:20px;background:#2dd4bf;color:#042f2e;width:31px;
  height:31px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-weight:bold;font-size:16px}
.pstep b{display:block;font-size:22px;margin:10px 0 12px;color:#5eead4}
.pstep p{color:#94a3b8;font-size:15.5px;line-height:1.65}
/* weights */
.wrow{display:flex;align-items:center;gap:18px;margin-bottom:13px}
.wlbl{width:230px;font-size:17px;flex:0 0 auto}
.wbar{flex:1;height:26px;background:#111b2e;border-radius:6px;overflow:hidden}
.wbar>i{display:block;height:100%;width:0;background:linear-gradient(90deg,#0ea5e9,#2dd4bf);
  transition:width .9s ease}
.wval{width:52px;color:#5eead4;font-weight:bold;font-size:17px;text-align:left;direction:ltr}
/* files */
.cards{display:flex;gap:22px}
.fcard{flex:1;background:#0f1a2e;border:1px solid #1e293b;border-radius:14px;padding:24px}
.fcard code{font-family:"DejaVu Sans Mono",monospace;color:#5eead4;font-size:17px;direction:ltr;display:block}
.fcard .tag{color:#2dd4bf;font-size:14px;margin:10px 0 14px;font-weight:bold}
.fcard p{color:#cbd5e1;font-size:16px;line-height:1.7;margin-bottom:16px}
.fcard li{list-style:none;color:#94a3b8;font-size:14.5px;font-family:"DejaVu Sans Mono",monospace;
  direction:ltr;text-align:right;padding:6px 0;border-top:1px solid #1a2740;unicode-bidi:plaintext}
/* gate */
.grow{display:flex;gap:18px;align-items:center;padding:19px 22px;border-radius:12px;margin-bottom:13px;
  background:#0f1a2e;border:1px solid #1e293b}
.gdot{width:15px;height:15px;border-radius:50%;flex:0 0 auto}
.gname{width:66px;font-weight:bold;font-size:19px;flex:0 0 auto}
.gwhen{flex:1;color:#cbd5e1;font-size:16px}
.gact{color:#94a3b8;font-size:15px;width:290px;flex:0 0 auto;text-align:left;direction:rtl}
/* learning */
.lcols{display:flex;gap:30px;align-items:center}
.lcol{flex:1}
.lhead{color:#94a3b8;font-size:15px;margin-bottom:14px;text-align:center}
.lrow{display:flex;justify-content:space-between;background:#0f1a2e;border:1px solid #1e293b;
  padding:14px 18px;border-radius:9px;margin-bottom:9px;font-size:17px}
.lval{font-family:"DejaVu Sans Mono",monospace;font-weight:bold;direction:ltr}
.up{color:#4ade80}.down{color:#f87171}.flat{color:#64748b}
.arrow{font-size:34px;color:#2dd4bf;flex:0 0 auto}
/* daily */
.cmd{background:#0f1a2e;border:1px solid #1e293b;border-radius:11px;padding:17px 22px;margin-bottom:13px}
.cmd code{font-family:"DejaVu Sans Mono",monospace;color:#5eead4;font-size:16.5px;direction:ltr;
  display:block;text-align:right;unicode-bidi:plaintext}
.cmd span{color:#94a3b8;font-size:15.5px;display:block;margin-top:7px}
/* status */
.scols{display:flex;gap:28px}
.scol{flex:1}
.scol h3{font-size:19px;margin-bottom:16px}
.sitem{display:flex;gap:11px;margin-bottom:13px;font-size:15.5px;line-height:1.6;color:#cbd5e1}
.sitem .m{flex:0 0 auto}
.sitem b{display:block;margin-bottom:4px}
.sitem p{color:#94a3b8;font-size:14.5px}
/* end */
.endlines{margin-top:30px}
.endlines p{font-size:22px;line-height:1.75;color:#cbd5e1;margin-bottom:20px;max-width:1040px}
.repo{margin-top:40px;font-family:"DejaVu Sans Mono",monospace;color:#5eead4;font-size:19px;
  direction:ltr;text-align:right}
"""


def esc(s):
    return html.escape(str(s))


def render(s, i):
    k = s["kind"]
    head = (f'<div class="rise"><div class="num">{s["num"]} —</div><h2>{esc(s["head"])}</h2></div>'
            if s.get("head") else "")
    if k == "title":
        return f'''<div class="rise"><div class="eyebrow">{esc(s["eyebrow"])}</div>
          <h1>{esc(s["title"])}</h1><div class="sub">{esc(s["sub"])}</div></div>
          <div class="quote rise">{s["quote"]}</div>'''
    if k == "bullets":
        items = "".join(f'<div class="bul rise"><div class="ico">{ic}</div><div><b>{esc(t)}</b>'
                        f'<p>{esc(d)}</p></div></div>' for ic, t, d in s["items"])
        return head + f'<div class="intro rise">{esc(s["intro"])}</div>' + items
    if k == "position":
        words = f'<span class="x">×</span>'.join(f'<span class="word">{esc(w)}</span>' for w in s["words"])
        return head + f'''<div class="words rise">{words}</div>
          <div class="posline rise">{esc(s["line"])}</div>
          <div class="foot rise">{esc(s["note"])}</div>'''
    if k == "tree":
        rows = "".join(f'<div class="row {cls} rise"><code>{esc(p)}</code><span>{esc(d)}</span></div>'
                       for p, d, cls in s["rows"])
        return head + rows
    if k == "pipeline":
        steps = "".join(f'<div class="pstep rise"><div class="pn">{n}</div><b>{esc(t)}</b>'
                        f'<p>{esc(d)}</p></div>' for t, d, n in s["steps"])
        return head + f'<div class="pipe">{steps}</div>' + \
            '<div class="foot rise">كل حدث = عنقود واحد = منشور واحد على الأكثر. خمسة مواقع تنقل الخبر نفسه لا تصبح خمسة منشورات.</div>'
    if k == "weights":
        rows = "".join(f'<div class="wrow rise"><div class="wlbl">{esc(l)}</div>'
                       f'<div class="wbar"><i data-w="{v*4}"></i></div>'
                       f'<div class="wval">{v}%</div></div>' for l, v in s["bars"])
        return head + rows + f'<div class="foot rise">{esc(s["foot"])}</div>'
    if k == "files":
        cards = "".join(f'''<div class="fcard rise"><code>{esc(c)}</code>
          <div class="tag">{esc(tag)}</div><p>{d}</p>
          <ul>{"".join(f"<li>{esc(x)}</li>" for x in lines)}</ul></div>'''
                        for c, tag, d, lines in s["cards"])
        return head + f'<div class="cards">{cards}</div>'
    if k == "gate":
        colors = {"green": "#4ade80", "yellow": "#fbbf24", "red": "#f87171"}
        rows = "".join(f'<div class="grow rise"><i class="gdot" style="background:{colors[c]}"></i>'
                       f'<div class="gname" style="color:{colors[c]}">{esc(n)}</div>'
                       f'<div class="gwhen">{esc(w)}</div><div class="gact">{esc(a)}</div></div>'
                       for c, n, w, a in s["rows"])
        return head + rows + f'<div class="foot rise">{esc(s["foot"])}</div>'
    if k == "learning":
        def col(items, after=False):
            out = []
            for name, v in items:
                cls = "flat" if v == 1.0 else ("up" if v > 1 else "down")
                out.append(f'<div class="lrow rise"><span>{esc(name)}</span>'
                           f'<span class="lval {cls if after else "flat"}">{v:.2f}×</span></div>')
            return "".join(out)
        return head + f'''<div class="lcols">
          <div class="lcol"><div class="lhead">قبل القياس</div>{col(s["before"])}</div>
          <div class="arrow rise">←</div>
          <div class="lcol"><div class="lhead">بعد ١٥ منشوراً مقيساً</div>{col(s["after"], True)}</div>
        </div><div class="foot rise">{esc(s["foot"])}</div>'''
    if k == "daily":
        cmds = "".join(f'<div class="cmd rise"><code>{esc(c)}</code><span>{esc(d)}</span></div>'
                       for c, d in s["cmds"])
        return head + cmds
    if k == "status":
        done = "".join(f'<div class="sitem rise"><span class="m accent">✔</span><span>{esc(d)}</span></div>'
                       for d in s["done"])
        todo = "".join(f'<div class="sitem rise"><span class="m" style="color:#fbbf24">▸</span>'
                       f'<span><b>{esc(t)}</b><p>{esc(d)}</p></span></div>' for t, d in s["todo"])
        return head + f'''<div class="scols">
          <div class="scol"><h3 class="accent">جاهز ويعمل</h3>{done}</div>
          <div class="scol"><h3 style="color:#fbbf24">ينتظرك أنت</h3>{todo}</div></div>'''
    if k == "end":
        lines = "".join(f'<p class="rise">{esc(l)}</p>' for l in s["lines"])
        return f'<div class="rise"><h2>{esc(s["title"])}</h2></div><div class="endlines">{lines}</div>' \
               f'<div class="repo rise">{esc(s["repo"])}</div>'
    return ""


def build(out: Path):
    scenes = "".join(f'<div class="scene" id="s{i}">'
                     f'<div class="chip">جولة في النظام · {i+1}/{len(SCENES)}</div>'
                     f'{render(s, i)}</div>' for i, s in enumerate(SCENES))
    times = json.dumps([s["t"] for s in SCENES])
    out.write_text(f"""<!doctype html><html lang="ar"><head><meta charset="utf-8">
<title>جولة في النظام</title><style>{CSS}</style></head><body>
{scenes}
<div class="progress"><i id="bar"></i></div>
<script>
const T = {times};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const bar = document.getElementById('bar');
const total = T.reduce((a,b)=>a+b,0);
(async () => {{
  await sleep(600);
  let elapsed = 0;
  for (let i = 0; i < T.length; i++) {{
    const sc = document.getElementById('s' + i);
    document.querySelectorAll('.scene').forEach(x => x.classList.remove('on'));
    sc.classList.add('on');
    const rises = sc.querySelectorAll('.rise');
    const budget = T[i] * 1000;
    const stagger = Math.min(420, (budget * 0.42) / Math.max(1, rises.length));
    for (const el of rises) {{ el.classList.add('in'); await sleep(stagger); }}
    sc.querySelectorAll('.wbar > i').forEach(b => b.style.width = b.dataset.w + 'px');
    const used = stagger * rises.length;
    const t0 = performance.now(), rest = Math.max(900, budget - used - 550);
    await new Promise(res => {{
      const step = now => {{
        const k = Math.min(1, (now - t0) / rest);
        bar.style.width = ((elapsed + used + rest * k) / (total * 1000) * 100) + '%';
        k < 1 ? requestAnimationFrame(step) : res();
      }};
      requestAnimationFrame(step);
    }});
    elapsed += used + rest;
    await sleep(550);
    rises.forEach(el => el.classList.remove('in'));
  }}
  bar.style.width = '100%';
  await sleep(900);
  window.__done = true;
}})();
</script></body></html>""", encoding="utf-8")
    print(f"built {out} — {len(SCENES)} scenes")


if __name__ == "__main__":
    build(HERE / "walkthrough.html")
