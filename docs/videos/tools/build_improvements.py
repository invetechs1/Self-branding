#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني صفحة «التحسينات السبعة» — 12 مشهداً: المشكلة ← ما بُني ← النتيجة.

    python docs/videos/tools/build_improvements.py       # ينتج improvements.html
    python docs/videos/tools/shots.py improvements.html 1 3 7
    python docs/videos/tools/record.py improvements.html 06-seven-improvements.mp4

عدّل SCENES أدناه ثم أعد البناء والتسجيل. لا تحتاج أي مفاتيح.
"""

import html, json
from pathlib import Path

HERE = Path(__file__).resolve().parent

SCENES = [
dict(kind="title", t=13,
     eyebrow="ما تغيّر في النظام",
     title="سبعة تحسينات",
     sub="من محرك يعمل — إلى محرك يتعلّم ويقيس الهدف الصحيح",
     quote="النظام كان يقيس الإعجابات ويظن أنه يخدم هدفك.<br>"
           "بعد هذه السبعة: يتعلّم ما يجلب <b>فرص أعمال</b>، ويكتب بصوتك أنت، "
           "ويلتقط القرار الحكومي قبل أن ينقله أحد."),

dict(kind="grid", t=20, num="00", head="السبعة في لوحة واحدة",
     cards=[("١", "صوتك الشخصي", "عيّنات بقلمك يقلّد إيقاعها", "ready"),
            ("٢", "القرارات الحكومية", "كشط صفحات ٨ جهات بلا RSS", "ready"),
            ("٣", "قصص بياناتك", "أرقامك التشغيلية بحواجز سرية", "ready"),
            ("٤", "المواعيد تتعلّم", "من أدائك داخل نوافذ استراتيجيتك", "live"),
            ("٥", "سحب المقاييس", "آلياً بدل التعبئة اليدوية", "live"),
            ("٦", "الفرص الواردة", "قياس الهدف لا الضجيج", "live"),
            ("٧", "رادار الردود", "اقتراح لا نشر — ضمان بنيوي", "live")]),

dict(kind="improve", t=17, num="٠١", head="صوتك الشخصي",
     problem="النظام كان يعرف <b>ماذا</b> تكتب، ولا يعرف <b>كيف تتكلم أنت</b>. "
             "القواعد وحدها تنتج نصاً صحيحاً بلا بصمة.",
     solution=["<code>profile/voice-samples.md</code>: ستة أقسام تكتب فيها بقلمك",
               "تفضيلات ملزمة: طول الجملة · اللهجة · الافتتاح والختام · كلمات ممنوعة",
               "تُحقن كمرجع <b>أسلوب لا معلومات</b> — يقلّد إيقاعك ولا يقتبس وقائعك"],
     result="الملف الفارغ لا يضرّ: يكتب بالقواعد العامة ولا يخترع صوتاً.",
     waiting="ينتظر عيّناتك — ولا يستطيع أحد كتابتها نيابةً عنك"),

dict(kind="improve", t=19, num="٠٢", head="مرصد القرارات الحكومية",
     problem="أثمن محتوى لجمهورك كان «متابعة يدوية» — أي أنه لن يحدث. "
             "أكثر الجهات لا تملك تغذية RSS أصلاً.",
     solution=["استخراج بمستويين: محددات CSS صريحة، أو تلقائي يجد قائمة الأخبار بنفسه",
               "يتجاهل روابط التنقل والتذييل، ويعمل مع تصميمات مختلفة تماماً",
               "٨ جهات: الموارد البشرية · التأمينات · هيئة المقاولين · زاتكا · البلديات ..."],
     result="خبر الجهة يُصنَّف رسمياً (مصداقية ١٠٠) وعمود «قرارات حكومية»، "
            "ويُحسب سعودياً بحكم مصدره ولو خلا عنوانه من ذكر السعودية.",
     bug="الاختبارات أمسكت خللاً صامتاً: المواقع العربية التي لا تذكر الترميز في "
         "ترويسة HTTP كانت تُفكَّك لاتينياً، فيتحول النص إلى رموز مشوّهة وتسقط "
         "أخبار الجهة كلها دون أن يلاحظ أحد."),

dict(kind="gate", t=18, num="٠٣", head="قصص بياناتك — حواجز مفروضة برمجياً",
     intro="المحتوى الوحيد الذي لا يستطيع منافس نسخه: ما تقيسه أنت في عزوم والعراب. "
           "وهو أخطر محتوى على السرية — فالبنية تبدأ بالحواجز لا بالثقة.",
     rows=[("حد التجميع: ٥ حالات", "رقم من حالة واحدة قد يكشف مشروعاً بعينه"),
           ("وجوب ذكر الأساس", "«٤٧ يوماً» ادعاء · «٤٧ يوماً من ١٨ مستخلصاً» بيان"),
           ("منع المبالغ المطلقة", "نسب ومدد وأعداد فقط — ولو في الزاوية"),
           ("internal / never", "أرقام لا تخرج في منشور إطلاقاً"),
           ("إلزام المراجعة", "قصة البيانات لا تكون خضراء أبداً مهما بدا النص آمناً")],
     foot="والملف يصلك بقيم فارغة عمداً — لم يُخترع لك رقم واحد."),

dict(kind="before_after", t=16, num="٠٤", head="المواعيد تتعلّم — داخل استراتيجيتك",
     before_title="قبل", after_title="بعد",
     before=["<code>POST_TIMES</code> مكتوبة ثابتة في الكود",
             "التعلّم يحسب أفضل الأوقات… ثم لا أحد يقرأها",
             "تغيير الموعد يحتاج تعديل سطر برمجي"],
     after=["متعلَّم ← افتراضي من <code>persona.yml</code> ← احتياطي",
            "كل مسودة تحمل مصدر موعدها في ملاحظات المراجعة",
            "أفضل أيام الأسبوع تُعرض <b>إرشادياً</b> — القرار قرارك"],
     foot="الحارس: التعلّم محصور داخل النوافذ الذهبية لاستراتيجيتك. "
          "منشور نجح الثالثة فجراً لا يصير موعد نشرك — الوقت خارج النافذة يُرفض "
          "مهما علا تفاعله، والعيّنة دون ٣ منشورات لا تُعتمد."),

dict(kind="table", t=17, num="٠٥", head="سحب المقاييس آلياً",
     intro="محرك التعلّم كان معلّقاً على تعبئتك اليدوية — أي أنه كان سيتوقف بعد أسبوعين.",
     headers=["المنصة", "ما تعطيه فعلاً"],
     rows=[["X", "انطباعات · إعجابات · ردود · إعادة نشر واقتباس · حفظ"],
           ["تيك توك", "مشاهدات · إعجابات · تعليقات · مشاركات"],
           ["لينكدإن", "إعجابات وتعليقات فقط — <b>الانطباعات غير متاحة</b> للحساب الشخصي"]],
     foot="ثغرة لازمة أُصلحت أولاً: معرّف المنشور كان يذهب في نص حر ولا يُخزَّن، "
          "فالقياس مستحيل بدونه. وثريد X صار يخزّن معرّف <b>رأس الثريد</b> — "
          "لأنه ما يفتحه الناس. وما تعبّئه يدوياً لا يمحوه السحب الآلي."),

dict(kind="weights", t=18, num="٠٦", head="الفرص الواردة — تغيير اتجاه التعلّم",
     intro="الهدف المعلن ليس المتابعين بل فرص الأعمال. ولم يكن في النظام ما يقيسه.",
     bars=[("تفاعل الجمهور", 40, "#0ea5e9"), ("الفرص الواردة", 40, "#2dd4bf"),
           ("تفضيلك: اعتماد ورفض", 20, "#64748b")],
     example="مثال فعلي: عمود «القرارات الحكومية» جلب ٣ فرص (منها فوز) وعمود "
             "«الذكاء الاصطناعي» جلب فرصتين ضعيفتين ← وزن الأول ارتفع والثاني انخفض، "
             "بصرف النظر عن أيّهما نال إعجابات أكثر.",
     foot="وحارس ضد التسرّع: عمود بفرصة واحدة يبقى محايداً — فرصة واحدة ليست نمطاً. "
          "والسجل بلا أسماء ولا أرقام ولا مبالغ."),

dict(kind="improve", t=17, num="٠٧", head="رادار الردود",
     problem="استراتيجيتك تنص على «١٠ ردود ذكية يومياً» — والنظام لا يفعل شيئاً هناك. "
             "والردود هي ما ينمّي حساب X فعلياً.",
     solution=["ترشيح: تقاطع مع أنشطتك × سرعة التفاعل × الحداثة",
               "يستبعد: ما مضى ٦ ساعات · ضعيف التفاعل · الجدلي والسياسي · ما رددتَ عليه",
               "زاوية الرد من الموضوع الغالب: القرار ← ترجمة عملية · العيب ← السبب الهندسي"],
     result="يقترح ولا يرد. <b>الضمان بنيوي:</b> لا دالة نشر رد في الملف إطلاقاً، "
            "ولا يستورد طبقة النشر، وفحصان يتأكدان من ذلك عند كل دفع.",
     waiting="الرد الآلي مخالف لشروط المنصات، والرد المصطنع يُكتشف ويضرّ السمعة"),

dict(kind="numbers", t=15, num="٠٨", head="الأثر بالأرقام",
     stats=[("٢٤٤", "فحصاً آلياً", "كانت ١٢٧ قبل هذه الجولة"),
            ("٨", "أخطاء حقيقية", "أمسكتها الاختبارات قبل الإنتاج"),
            ("٦", "وحدات جديدة", "صوت · حكومة · بيانات · مقاييس · فرص · ردود"),
            ("٠", "أسرار في المستودع", "فحص آلي عند كل دفع")],
     foot="أبرز ما أُمسك: ترميز عربي مشوّه يُسقط أخبار جهة كاملة بصمت · "
          "معرّف منشور لا يُخزَّن فيستحيل القياس · دالة تسمح بإعادة نشر منشور سابق · "
          "اختبار صوري كتبته بشرط يجعله ينجح دائماً."),

dict(kind="status", t=17, num="٠٩", head="أين نحن — وما ينتظرك",
     done=["٤ و٥ و٦ و٧ تعمل الآن بلا تدخل منك",
           "١ و٢ و٣ بنيتها جاهزة ومختبرة — تنتظر مادتك أنت",
           "كل شيء مدفوع إلى GitHub ويُختبر آلياً عند كل دفع"],
     todo=[("عيّنات صوتك", "فقرة أو اثنتان بقلمك — ولو من واتساب"),
           ("ثلاثة أرقام تشغيلية", "مدة تحصيل المستخلص · نسبة أوامر التغيير · أسباب التأخير (مع «من كم حالة»)"),
           ("فحص على جهازك", "gov_watch.py --check · news_engine.py --check-sources")]),

dict(kind="end", t=13,
     title="ملاحظة صريحة",
     lines=["كل ما بُني مُختبر منطقياً — لكنه <b>لم يلمس منصة أو موقعاً حقيقياً بعد</b>. "
            "لا مفاتيح في بيئة التطوير، والشبكة محجوبة عن مواقع الأخبار.",
            "أول تشغيل على جهازك سيكشف أشياء: روابط ميتة، محددات تغيّرت، صلاحيات ناقصة. "
            "هذا متوقع وطبيعي — أرسل أي خطأ يظهر وأصلحه."],
     repo="github.com/invetechs1/Self-branding"),
]


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1280px;height:720px;overflow:hidden;background:#0a0f1c;color:#e2e8f0;
  font-family:"DejaVu Sans",sans-serif;direction:rtl}
.scene{position:absolute;inset:0;padding:44px 60px 54px;opacity:0;transform:translateY(14px);
  transition:opacity .55s ease,transform .55s ease;display:flex;flex-direction:column;
  justify-content:center}
.scene.on{opacity:1;transform:none}
.rise{opacity:0;transform:translateY(12px);transition:opacity .5s ease,transform .5s ease}
.rise.in{opacity:1;transform:none}
.num{color:#2dd4bf;font-size:13px;letter-spacing:3px;margin-bottom:6px;font-weight:bold}
h1{font-size:42px;line-height:1.22;font-weight:bold;letter-spacing:-.5px}
h2{font-size:30px;line-height:1.3;font-weight:bold;margin-bottom:22px;letter-spacing:-.4px}
.accent{color:#2dd4bf}.muted{color:#94a3b8}
code{font-family:"DejaVu Sans Mono",monospace;font-size:.88em;color:#5eead4;
  background:#0f1a2e;padding:1px 6px;border-radius:4px;direction:ltr;unicode-bidi:embed}
b{color:#f1f5f9}
.foot{margin-top:24px;padding-top:14px;color:#94a3b8;font-size:14.5px;line-height:1.65;
  border-top:1px solid #1e293b}
.progress{position:absolute;left:0;right:0;bottom:0;height:4px;background:#111b2e}
.progress>i{display:block;height:100%;background:linear-gradient(90deg,#2dd4bf,#0ea5e9);width:0}
.chip{position:absolute;left:60px;top:44px;color:#475569;font-size:12.5px;letter-spacing:1px}
#s0 .chip,#s11 .chip{display:none}
/* title */
.eyebrow{color:#2dd4bf;font-size:16px;letter-spacing:5px;margin-bottom:18px}
.sub{color:#94a3b8;font-size:21px;margin-top:14px}
.quote{margin-top:42px;border-right:3px solid #2dd4bf;padding:20px 24px;background:#0f1a2e;
  border-radius:0 10px 10px 0;font-size:19.5px;line-height:1.85;color:#cbd5e1;max-width:1010px}
/* grid */
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.gcard{background:#0f1a2e;border:1px solid #1e293b;border-radius:13px;padding:18px 16px;
  position:relative;min-height:124px}
.gcard.live{border-color:#1e4c49}
.gnum{position:absolute;top:-13px;right:16px;width:28px;height:28px;border-radius:50%;
  background:#2dd4bf;color:#042f2e;display:flex;align-items:center;justify-content:center;
  font-weight:bold;font-size:14px}
.gcard b{display:block;font-size:17.5px;margin:8px 0 7px;color:#5eead4}
.gcard p{color:#94a3b8;font-size:13.5px;line-height:1.6}
.gstate{position:absolute;bottom:12px;left:16px;font-size:11px;padding:2px 9px;border-radius:9px}
.gstate.live{background:#042f2e;color:#5eead4;border:1px solid #1e4c49}
.gstate.ready{background:#2a2112;color:#fbbf24;border:1px solid #4a3a16}
/* improve */
.block{margin-bottom:17px}
.blabel{color:#2dd4bf;font-size:14px;font-weight:bold;margin-bottom:7px}
.ptext{font-size:18.5px;line-height:1.7;color:#cbd5e1}
.slist li{list-style:none;color:#cbd5e1;font-size:16.5px;line-height:1.7;padding:4px 0 4px 0;
  padding-right:20px;position:relative}
.slist li:before{content:"▸";position:absolute;right:0;color:#2dd4bf}
.rtext{background:#0f1a2e;border-right:3px solid #2dd4bf;padding:14px 18px;border-radius:0 9px 9px 0;
  font-size:16.5px;line-height:1.7;color:#cbd5e1}
.warn{background:#1a1410;border-right:3px solid #fbbf24;padding:14px 18px;border-radius:0 9px 9px 0;
  font-size:15.5px;line-height:1.7;color:#d6cfc4;margin-top:14px}
.waiting{margin-top:14px;color:#fbbf24;font-size:15px}
/* gate / table rows */
.grow{display:flex;gap:18px;align-items:flex-start;padding:14px 20px;border-radius:11px;
  margin-bottom:9px;background:#0f1a2e;border:1px solid #1e293b}
.gkey{width:230px;flex:0 0 auto;font-weight:bold;font-size:16.5px;color:#5eead4}
.gval{flex:1;color:#cbd5e1;font-size:16px;line-height:1.6}
.intro{color:#cbd5e1;font-size:17.5px;line-height:1.7;margin-bottom:20px}
/* before/after */
.cols{display:flex;gap:24px;align-items:stretch}
.col{flex:1;background:#0f1a2e;border:1px solid #1e293b;border-radius:13px;padding:20px}
.col.after{border-color:#1e4c49}
.ctitle{font-size:15px;margin-bottom:14px;color:#94a3b8;text-align:center}
.col.after .ctitle{color:#5eead4}
.col li{list-style:none;color:#cbd5e1;font-size:16px;line-height:1.65;padding:8px 0;
  border-top:1px solid #1a2740}
.col li:first-child{border-top:0}
/* weights */
.wrow{display:flex;align-items:center;gap:18px;margin-bottom:15px}
.wlbl{width:230px;font-size:17.5px;flex:0 0 auto}
.wbar{flex:1;height:30px;background:#111b2e;border-radius:7px;overflow:hidden}
.wbar>i{display:block;height:100%;width:0;transition:width 1s ease}
.wval{width:54px;color:#5eead4;font-weight:bold;font-size:18px;text-align:left;direction:ltr}
.example{margin-top:18px;background:#0f1a2e;border-right:3px solid #0ea5e9;padding:14px 18px;
  border-radius:0 9px 9px 0;font-size:16px;line-height:1.7;color:#cbd5e1}
/* numbers */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.stat{background:#0f1a2e;border:1px solid #1e293b;border-radius:13px;padding:22px 18px;text-align:center}
.stat .big{font-size:42px;font-weight:bold;color:#2dd4bf;line-height:1}
.stat .lbl{font-size:16px;margin:10px 0 7px;color:#e2e8f0}
.stat .sub{font-size:13px;color:#94a3b8;line-height:1.55}
/* status */
.scols{display:flex;gap:28px}
.scol{flex:1}
.scol h3{font-size:19px;margin-bottom:15px}
.sitem{display:flex;gap:11px;margin-bottom:13px;font-size:16px;line-height:1.65;color:#cbd5e1}
.sitem .m{flex:0 0 auto}
.sitem b{display:block;margin-bottom:3px}
.sitem p{color:#94a3b8;font-size:14.5px}
/* end */
.endlines p{font-size:20px;line-height:1.8;color:#cbd5e1;margin-bottom:18px;max-width:1040px}
.repo{margin-top:34px;font-family:"DejaVu Sans Mono",monospace;color:#5eead4;font-size:19px;
  direction:ltr;text-align:right}
"""


def e(s):
    return html.escape(str(s))


def render(s):
    k = s["kind"]
    head = (f'<div class="rise"><div class="num">{s["num"]} —</div><h2>{e(s["head"])}</h2></div>'
            if s.get("head") else "")
    if k == "title":
        return (f'<div class="rise"><div class="eyebrow">{e(s["eyebrow"])}</div>'
                f'<h1>{e(s["title"])}</h1><div class="sub">{e(s["sub"])}</div></div>'
                f'<div class="quote rise">{s["quote"]}</div>')
    if k == "grid":
        cards = "".join(
            f'<div class="gcard {st} rise"><div class="gnum">{n}</div><b>{e(t)}</b>'
            f'<p>{e(d)}</p><span class="gstate {st}">'
            f'{"يعمل الآن" if st == "live" else "ينتظر مادتك"}</span></div>'
            for n, t, d, st in s["cards"])
        return head + f'<div class="grid">{cards}</div>'
    if k == "improve":
        parts = [head,
                 f'<div class="block rise"><div class="blabel">المشكلة</div>'
                 f'<div class="ptext">{s["problem"]}</div></div>',
                 '<div class="block rise"><div class="blabel">ما بُني</div><ul class="slist">'
                 + "".join(f"<li>{x}</li>" for x in s["solution"]) + "</ul></div>",
                 f'<div class="rise rtext">{s["result"]}</div>']
        if s.get("bug"):
            parts.append(f'<div class="rise warn"><b>⚠ خلل أُمسك قبل الإنتاج:</b> {s["bug"]}</div>')
        if s.get("waiting"):
            parts.append(f'<div class="rise waiting">◆ {s["waiting"]}</div>')
        return "".join(parts)
    if k == "gate":
        rows = "".join(f'<div class="grow rise"><div class="gkey">{e(a)}</div>'
                       f'<div class="gval">{b}</div></div>' for a, b in s["rows"])
        return (head + f'<div class="intro rise">{e(s["intro"])}</div>' + rows
                + f'<div class="foot rise">{e(s["foot"])}</div>')
    if k == "table":
        rows = "".join(f'<div class="grow rise"><div class="gkey">{e(r[0])}</div>'
                       f'<div class="gval">{r[1]}</div></div>' for r in s["rows"])
        return (head + f'<div class="intro rise">{e(s["intro"])}</div>' + rows
                + f'<div class="foot rise">{s["foot"]}</div>')
    if k == "before_after":
        def col(title, items, cls=""):
            lis = "".join(f"<li>{x}</li>" for x in items)
            return f'<div class="col {cls} rise"><div class="ctitle">{e(title)}</div><ul>{lis}</ul></div>'
        return (head + '<div class="cols">' + col(s["before_title"], s["before"])
                + col(s["after_title"], s["after"], "after") + "</div>"
                + f'<div class="foot rise">{e(s["foot"])}</div>')
    if k == "weights":
        rows = "".join(
            f'<div class="wrow rise"><div class="wlbl">{e(l)}</div>'
            f'<div class="wbar"><i data-w="{v * 7}" style="background:{c}"></i></div>'
            f'<div class="wval">{v}%</div></div>' for l, v, c in s["bars"])
        return (head + f'<div class="intro rise">{e(s["intro"])}</div>' + rows
                + f'<div class="example rise">{e(s["example"])}</div>'
                + f'<div class="foot rise">{e(s["foot"])}</div>')
    if k == "numbers":
        stats = "".join(f'<div class="stat rise"><div class="big">{e(b)}</div>'
                        f'<div class="lbl">{e(l)}</div><div class="sub">{e(sb)}</div></div>'
                        for b, l, sb in s["stats"])
        return head + f'<div class="stats">{stats}</div>' + f'<div class="foot rise">{s["foot"]}</div>'
    if k == "status":
        done = "".join(f'<div class="sitem rise"><span class="m accent">✔</span>'
                       f'<span>{e(d)}</span></div>' for d in s["done"])
        todo = "".join(f'<div class="sitem rise"><span class="m" style="color:#fbbf24">▸</span>'
                       f'<span><b>{e(t)}</b><p>{e(d)}</p></span></div>' for t, d in s["todo"])
        return head + (f'<div class="scols"><div class="scol"><h3 class="accent">يعمل الآن</h3>{done}</div>'
                       f'<div class="scol"><h3 style="color:#fbbf24">ينتظرك أنت</h3>{todo}</div></div>')
    if k == "end":
        lines = "".join(f'<p class="rise">{x}</p>' for x in s["lines"])
        return (f'<div class="rise"><h2>{e(s["title"])}</h2></div>'
                f'<div class="endlines">{lines}</div>'
                f'<div class="repo rise">{e(s["repo"])}</div>')
    return ""


def build(out: Path):
    scenes = "".join(f'<div class="scene" id="s{i}">'
                     f'<div class="chip">التحسينات السبعة · {i + 1}/{len(SCENES)}</div>'
                     f'{render(s)}</div>' for i, s in enumerate(SCENES))
    out.write_text(f"""<!doctype html><html lang="ar"><head><meta charset="utf-8">
<title>التحسينات السبعة</title><style>{CSS}</style></head><body>
{scenes}<div class="progress"><i id="bar"></i></div>
<script>
const T = {json.dumps([s["t"] for s in SCENES])};
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
    const stagger = Math.min(430, (budget * 0.45) / Math.max(1, rises.length));
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
    build(HERE / "improvements.html")
