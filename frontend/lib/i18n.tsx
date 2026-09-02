"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Locale = "en" | "ar";

const dict = {
  en: {
    common: {
      loading: "Loading…", error: "Error", cancel: "Cancel", save: "Save", add: "Add",
      edit: "Edit", signIn: "Sign in", signingIn: "Signing in…", signOut: "Sign out",
      languageSwitch: "العربية",
    },
    shell: {
      brandName: "Yahya Intelligence", brandSub: "Content assistant",
      navToday: "Today's Intelligence", navOpportunities: "Content Opportunities",
      navDrafts: "Drafts & Approval", navPerformance: "Performance & Learning", navSettings: "Settings",
      todayTitle: "Today's Intelligence", todaySub: "What matters to you, filtered from the noise",
      opportunitiesTitle: "Content Opportunities", opportunitiesSub: "What you should talk about next",
      draftsTitle: "Drafts & Approval", draftsSub: "Review queue",
      performanceTitle: "Performance & Learning", performanceSub: "What's working, and why",
      settingsTitle: "Settings", settingsSub: "Configure your virtual assistant",
      liveConnected: "Live — connected to backend",
    },
    login: {
      email: "Email", password: "Password", signInFailed: "Sign in failed",
      genericError: "Something went wrong — try again.",
    },
    today: {
      greetMorning: "Good morning", greetAfternoon: "Good afternoon", greetEvening: "Good evening",
      subtitle: "Here's what matters today — ranked, explained, and ready to act on.",
      fetchLatest: "Fetch latest", fetching: "Fetching…",
      checkingSources: "Checking 17 sources — this takes about a minute. You can keep browsing; this updates automatically.",
      lastFetch: "Last fetch: {kept} new {storyWord} from {fetched} articles checked ({time}).",
      storySingular: "story", storyPlural: "stories",
      lastFetchFailed: "Last fetch failed: {error}",
      statsAnalyzed: "Stories analyzed today", statsAttention: "Needing your attention",
      emptyTitle: "No intelligence yet", emptyBody: "Click “Fetch latest” above to pull in today's stories.",
      viewInOpportunities: "View in Opportunities",
      relevantTo: "Relevant to {pillar}", inRegion: " in {region}",
      corroborated: ", corroborated by {count} {sourceWord}.",
      sourceSingular: "source", sourcePlural: "sources",
    },
    opportunities: {
      errorPrefix: "Error", loading: "Loading…",
      emptyTitle: "No opportunities yet",
      emptyBody: "Once today's intelligence surfaces something worth saying, it will show up here.",
      labelPrefix: "Label:", createDraft: "Create Draft", generating: "Generating…", dismiss: "Dismiss",
      sourceSingular: "source", sourcePlural: "sources",
      typeBassirFeature: "Product opportunity", typePartnership: "Partnership",
      typeInvestmentTheme: "Investment thesis", typeCompetitiveIntel: "Competitive intel",
      platformLinkedin: "LinkedIn", platformX: "X", platformXThread: "X Thread",
    },
    drafts: {
      reviewQueue: "Review queue", reviewedOf: "{reviewed} of {total} reviewed",
      filterAll: "All", filterNeedsReview: "Needs review", filterLinkedin: "LinkedIn", filterX: "X", filterRed: "🔴 Red",
      loading: "Loading…", nothingHere: "Nothing here", noMatchFilter: "No drafts match this filter.",
      needsReview: "needs review", allCaughtUp: "All caught up", noDraftsToReview: "No drafts to review right now.",
      approved: "Approved",
      editDraft: "Edit draft", mediaBrief: "Media brief",
      scoreBreakdown: "Relevance score breakdown", sourcesAndRefs: "Sources & references ({count})",
      whyReject: "Why reject?", confirmReject: "Confirm reject", cancel: "Cancel",
      redConfirmText: "This draft is flagged red — sensitive, unverified, or high-risk content. Approving it publishes under Yahya's name without further review.",
      yesApproveAnyway: "Yes, approve anyway",
      requiresSignoff: "Requires explicit sign-off", approve: "Approve",
      publishNow: "Publish now", scheduledManual: "Scheduled — publish manually on the platform",
      published: "Published", publishFailedRetry: "Publish failed — retry", reviewed: "Reviewed",
      cancelEdit: "Cancel edit", saveApprove: "Save & Approve", reject: "Reject", regenerate: "Regenerate",
      kbdApprove: "pprove", kbdEdit: "dit", kbdReject: "eject", kbdNext: "ext",
      pts: "pts", errorPrefix: "Error",
      reasonGreen: "No safety flags raised.", reasonYellow: "Contains opinion, prediction, or unverified detail.",
      reasonRed: "Sensitive content or unverified claim — human sign-off required.",
      labelRed: "High risk — human sign-off required.", labelYellow: "Opinion / prediction.", labelVerified: "Verified / educational.",
      characters: "characters",
    },
    performance: {
      errorPrefix: "Error", loading: "Loading…",
      postsPublished: "Posts published", avgEngagement: "Avg. engagement rate",
      approvalRate: "Approval rate", totalImpressions: "Total impressions",
      platformPerformance: "Platform performance", noPublishedMeasured: "No published posts measured yet.",
      whatLearned: "What the system learned", plainLanguage: "Plain-language summary — no jargon",
      notEnoughData: "Not enough data yet — needs at least 3 measured posts per topic before the system draws conclusions.",
      contentMix: "Content mix — target vs. actual",
      learningWeightNote: "Learning weight shown as a multiplier applied to future scoring",
      target: "target {pct}%", actual: "actual {pct}%",
      recomputeNow: "Recompute now", recomputing: "Recomputing…",
      publishedPosts: "Published posts", nothingPublished: "Nothing published yet",
      approveToSeePerf: "Approve and publish a draft to start seeing performance here.",
      colPost: "Post", colDate: "Date", colImpressions: "Impressions", colLikes: "Likes",
      colComments: "Comments", colShares: "Shares", colEngagement: "Engagement",
    },
    settings: {
      sections: {
        profile: "Profile", knowledge: "Knowledge / Facts", pillars: "Content Pillars",
        topics: "Topics", sources: "News Sources", social: "Social Accounts",
        publishing: "Publishing Rules", approval: "Approval Rules", safety: "Safety",
        learning: "Learning", system: "System Configuration",
      },
      profile: {
        nameAr: "Full name (Arabic)", nameEn: "Full name (English)", headline: "Headline", city: "City",
        notAdded: "Not added yet",
        cityHint: "Sourced from profile/facts.yml — edit that file and re-run scripts/seed.py to change it.",
        socialHandles: "Social handles", connected: "Connected", notConnected: "Not connected",
      },
      knowledge: {
        intro: "This is the only source of truth the system is allowed to draw on for anything said in your voice. Filling a gap here immediately improves how future drafts about that topic are written.",
        addFact: "+ Add a fact", title: "Title", body: "Body",
        public: "Public", private: "Private",
        kindBio: "Bio", kindProject: "Experience", kindCompany: "Ventures",
        kindProduct: "Products in development", kindQuote: "Philosophy & quotes",
        kindGoal: "Goals", kindEducation: "Education", kindOpinion: "Opinions",
      },
      pillars: {
        intro: "Target mix guides what the assistant looks for. Actual output is shown on the Performance screen, and the learning engine nudges within a 0.7×–1.4× band — it never lets a pillar drop to zero.",
        targetShare: "Target share of your content mix",
      },
      topics: {
        tier: "Tier {n}", tierHighest: " — highest weight",
        addTopicPlaceholder: "e.g. Green building, Hydrogen…",
        excludedTitle: "Excluded topics — never surfaced",
        none: "None excluded.", excludePlaceholder: "e.g. Politics", exclude: "Exclude",
      },
      sources: {
        colSource: "Source", colRegion: "Region", colCredibility: "Credibility",
        colLastFetched: "Last fetched", colEnabled: "Enabled", never: "Never",
      },
      social: {
        credentialsConfigured: "Credentials configured in the backend environment.",
        addCredentials: "Add credentials to backend/.env to connect.",
      },
      publishing: {
        autoGreen: "Auto-publish green content",
        lockedUntil: "Locked until {date} — your first 3 months stay fully manual, per your own approval policy. Nothing publishes without your review before then, regardless of safety level.",
        unlockedNote: "Manual period has ended — this can now be enabled, but stays off until you turn it on explicitly.",
        autoYellow: "Auto-publish yellow content",
        yellowNote: "Opinion or prediction content always requires manual approval, indefinitely.",
        autoRed: "Auto-publish red content",
        redNote: "Never available — sensitive or unverified content always requires explicit sign-off.",
      },
      approval: {
        pipelineEntry: "Pipeline entry score",
        pipelineEntryDesc: "Minimum relevance score for a story to enter the content pipeline at all.",
        deepDive: "Deep-dive threshold",
        deepDiveDesc: "Score above which a story is worth a full article or thread, not just a short post.",
        duplicateSimilarity: "Duplicate similarity",
        duplicateSimilarityDesc: "Headline similarity above this counts as “the same story” — prevents multiple posts about one event.",
        minCredibility: "Min. credibility for numeric claims",
        minCredibilityDesc: "A financial or statistical figure needs at least this source credibility to be usable.",
        factConfidenceAuto: "Fact confidence — auto-publish eligible",
        factConfidenceAutoDesc: "Below this, content is held for review regardless of safety color.",
        factConfidenceRed: "Fact confidence — forces red",
        factConfidenceRedDesc: "Below this, content is automatically classified red.",
      },
      safety: {
        green: "Green", greenDesc: "Verified public information or educational content. Eligible for auto-publish once your 3-month manual period ends.",
        yellow: "Yellow", yellowDesc: "Opinion, prediction, or business commentary. Always needs your review.",
        red: "Red", redDesc: "Sensitive, financial, legal, personal, or unverified. Never publishes automatically — ever.",
        neverExpose: "Never mentioned, under any circumstance",
        autoFlags: "Auto-flags as red",
      },
      learning: {
        intro: "The system slightly favors topics and formats that perform well, and slightly reduces ones that don't — informed by your approvals, edits, rejections, and published-post engagement. No pillar can ever be pushed below a 0.7× floor or above 1.4×.",
        currentMultiplier: "Current learning multiplier",
        recomputeNow: "Recompute now", recomputing: "Recomputing…",
      },
      system: {
        timezone: "Timezone", timezoneDesc: "Used for scheduling and posting-window preferences",
        cadence: "Discovery cadence", cadenceDesc: "How often sources are checked for new stories",
        defaultLang: "Default content language", defaultLangDesc: "Arabic first, English for global-facing angles",
        environment: "Environment", environmentDesc: "Deployment mode this backend is running in",
      },
    },
    badges: {
      componentPersonalInterest: "Personal Interest", componentBusinessRelevance: "Business Relevance",
      componentSaudiGcc: "Saudi / GCC Relevance", componentStrategic: "Strategic Importance",
      componentAudienceValue: "Audience Value", componentFreshness: "Freshness", componentCredibility: "Source Credibility",
      total: "Total", noBreakdown: "No score breakdown available.",
      noSources: "No external sources — sourced from verified Knowledge & Facts.",
      safetyGreen: "Verified / educational", safetyYellow: "Opinion / needs review", safetyRed: "High risk — sign-off required",
      confidenceHigh: "High", confidenceMedium: "Medium", confidenceLow: "Low", confidenceSuffix: "confidence",
    },
    pillars: {
      ai_technology: "AI & Technology", entrepreneurship: "Entrepreneurship",
      construction_engineering: "Construction & Engineering", real_estate: "Real Estate Development",
      saudi_economy: "Saudi Economy & Vision 2030", business_management: "Business Management",
      investment: "Investment", leadership_lessons: "Leadership & Lessons",
    },
  },
  ar: {
    common: {
      loading: "جارٍ التحميل…", error: "خطأ", cancel: "إلغاء", save: "حفظ", add: "إضافة",
      edit: "تعديل", signIn: "تسجيل الدخول", signingIn: "جارٍ تسجيل الدخول…", signOut: "تسجيل الخروج",
      languageSwitch: "English",
    },
    shell: {
      brandName: "منصة يحيى الذكية", brandSub: "مساعد المحتوى",
      navToday: "استخبارات اليوم", navOpportunities: "فرص المحتوى",
      navDrafts: "المسودات والاعتماد", navPerformance: "الأداء والتعلّم", navSettings: "الإعدادات",
      todayTitle: "استخبارات اليوم", todaySub: "ما يهمك اليوم، بعد تصفيته من الضجيج",
      opportunitiesTitle: "فرص المحتوى", opportunitiesSub: "ما يجدر بك الحديث عنه لاحقًا",
      draftsTitle: "المسودات والاعتماد", draftsSub: "قائمة المراجعة",
      performanceTitle: "الأداء والتعلّم", performanceSub: "ما ينجح، ولماذا",
      settingsTitle: "الإعدادات", settingsSub: "تهيئة مساعدك الرقمي",
      liveConnected: "مباشر — متصل بالخادم",
    },
    login: {
      email: "البريد الإلكتروني", password: "كلمة المرور", signInFailed: "فشل تسجيل الدخول",
      genericError: "حدث خطأ ما — يرجى المحاولة مرة أخرى.",
    },
    today: {
      greetMorning: "صباح الخير", greetAfternoon: "مساء الخير", greetEvening: "مساء الخير",
      subtitle: "إليك أهم ما يستحق اهتمامك اليوم — مرتّبًا، موضّحًا، وجاهزًا للتصرف.",
      fetchLatest: "جلب الأحدث", fetching: "جارٍ الجلب…",
      checkingSources: "جارٍ فحص 17 مصدرًا — يستغرق هذا نحو دقيقة. يمكنك متابعة التصفح؛ سيتحدث هذا تلقائيًا.",
      lastFetch: "آخر جلب: {kept} {storyWord} جديدة من أصل {fetched} مقالًا تم فحصها ({time}).",
      storySingular: "قصة", storyPlural: "قصص",
      lastFetchFailed: "فشل آخر جلب: {error}",
      statsAnalyzed: "القصص التي تم تحليلها اليوم", statsAttention: "بحاجة إلى اهتمامك",
      emptyTitle: "لا توجد استخبارات بعد", emptyBody: "اضغط على “جلب الأحدث” أعلاه لسحب قصص اليوم.",
      viewInOpportunities: "عرض في الفرص",
      relevantTo: "ذو صلة بـ {pillar}", inRegion: " في {region}",
      corroborated: "، مؤكَّد من {count} {sourceWord}.",
      sourceSingular: "مصدر", sourcePlural: "مصادر",
    },
    opportunities: {
      errorPrefix: "خطأ", loading: "جارٍ التحميل…",
      emptyTitle: "لا توجد فرص بعد",
      emptyBody: "بمجرد أن تُظهر استخبارات اليوم شيئًا يستحق الحديث عنه، سيظهر هنا.",
      labelPrefix: "التصنيف:", createDraft: "إنشاء مسودة", generating: "جارٍ الإنشاء…", dismiss: "تجاهل",
      sourceSingular: "مصدر", sourcePlural: "مصادر",
      typeBassirFeature: "فرصة منتج", typePartnership: "شراكة",
      typeInvestmentTheme: "أطروحة استثمارية", typeCompetitiveIntel: "استخبارات تنافسية",
      platformLinkedin: "لينكدإن", platformX: "إكس", platformXThread: "سلسلة تغريدات إكس",
    },
    drafts: {
      reviewQueue: "قائمة المراجعة", reviewedOf: "تمت مراجعة {reviewed} من {total}",
      filterAll: "الكل", filterNeedsReview: "بحاجة لمراجعة", filterLinkedin: "لينكدإن", filterX: "إكس", filterRed: "🔴 أحمر",
      loading: "جارٍ التحميل…", nothingHere: "لا يوجد شيء هنا", noMatchFilter: "لا توجد مسودات مطابقة لهذا الفلتر.",
      needsReview: "بحاجة لمراجعة", allCaughtUp: "لا شيء متبقٍّ", noDraftsToReview: "لا توجد مسودات للمراجعة الآن.",
      approved: "معتمدة",
      editDraft: "تعديل المسودة", mediaBrief: "موجز الوسائط",
      scoreBreakdown: "تفصيل درجة الصلة", sourcesAndRefs: "المصادر والمراجع ({count})",
      whyReject: "سبب الرفض؟", confirmReject: "تأكيد الرفض", cancel: "إلغاء",
      redConfirmText: "هذه المسودة مصنّفة أحمر — محتوى حساس أو غير موثّق أو عالي الخطورة. اعتمادها سيؤدي إلى نشرها باسم يحيى دون مراجعة إضافية.",
      yesApproveAnyway: "نعم، اعتمد على أي حال",
      requiresSignoff: "يتطلب موافقة صريحة", approve: "اعتماد",
      publishNow: "نشر الآن", scheduledManual: "مجدولة — يتم نشرها يدويًا على المنصة",
      published: "منشورة", publishFailedRetry: "فشل النشر — إعادة المحاولة", reviewed: "تمت مراجعتها",
      cancelEdit: "إلغاء التعديل", saveApprove: "حفظ واعتماد", reject: "رفض", regenerate: "إعادة توليد",
      kbdApprove: "عتماد", kbdEdit: "تعديل", kbdReject: "رفض", kbdNext: "لتالي",
      pts: "نقطة", errorPrefix: "خطأ",
      reasonGreen: "لم تُرفع أي أعلام أمان.", reasonYellow: "تحتوي على رأي أو تنبؤ أو تفصيل غير موثّق.",
      reasonRed: "محتوى حساس أو ادعاء غير موثّق — يتطلب موافقة بشرية.",
      labelRed: "خطورة عالية — يتطلب موافقة بشرية.", labelYellow: "رأي / تنبؤ.", labelVerified: "موثّق / تعليمي.",
      characters: "حرفًا",
    },
    performance: {
      errorPrefix: "خطأ", loading: "جارٍ التحميل…",
      postsPublished: "المنشورات المنشورة", avgEngagement: "متوسط معدل التفاعل",
      approvalRate: "معدل الاعتماد", totalImpressions: "إجمالي المشاهدات",
      platformPerformance: "أداء المنصات", noPublishedMeasured: "لا توجد منشورات منشورة تم قياسها بعد.",
      whatLearned: "ما تعلّمه النظام", plainLanguage: "ملخّص بلغة مبسّطة — بلا مصطلحات تقنية",
      notEnoughData: "لا توجد بيانات كافية بعد — يلزم 3 منشورات مقاسة على الأقل لكل موضوع قبل أن يخرج النظام باستنتاجات.",
      contentMix: "مزيج المحتوى — المستهدف مقابل الفعلي",
      learningWeightNote: "يظهر وزن التعلّم كمُضاعِف يُطبَّق على التقييم المستقبلي",
      target: "مستهدف {pct}٪", actual: "فعلي {pct}٪",
      recomputeNow: "إعادة الحساب الآن", recomputing: "جارٍ إعادة الحساب…",
      publishedPosts: "المنشورات المنشورة", nothingPublished: "لا يوجد شيء منشور بعد",
      approveToSeePerf: "اعتمد وانشر مسودة لتبدأ برؤية الأداء هنا.",
      colPost: "المنشور", colDate: "التاريخ", colImpressions: "المشاهدات", colLikes: "الإعجابات",
      colComments: "التعليقات", colShares: "المشاركات", colEngagement: "التفاعل",
    },
    settings: {
      sections: {
        profile: "الملف الشخصي", knowledge: "المعرفة / الحقائق", pillars: "محاور المحتوى",
        topics: "المواضيع", sources: "مصادر الأخبار", social: "الحسابات الاجتماعية",
        publishing: "قواعد النشر", approval: "قواعد الاعتماد", safety: "الأمان",
        learning: "التعلّم", system: "إعدادات النظام",
      },
      profile: {
        nameAr: "الاسم الكامل (عربي)", nameEn: "الاسم الكامل (إنجليزي)", headline: "العنوان الوظيفي", city: "المدينة",
        notAdded: "لم تُضَف بعد",
        cityHint: "مصدرها ملف profile/facts.yml — عدّل الملف وأعد تشغيل scripts/seed.py لتغييرها.",
        socialHandles: "الحسابات الاجتماعية", connected: "متصل", notConnected: "غير متصل",
      },
      knowledge: {
        intro: "هذا هو المصدر الوحيد الموثوق الذي يُسمح للنظام بالاعتماد عليه لأي شيء يُقال بصوتك. سد أي فجوة هنا يحسّن فورًا كيفية كتابة المسودات المستقبلية حول ذلك الموضوع.",
        addFact: "+ إضافة حقيقة", title: "العنوان", body: "المحتوى",
        public: "عام", private: "خاص",
        kindBio: "السيرة الذاتية", kindProject: "الخبرات", kindCompany: "المشاريع",
        kindProduct: "منتجات قيد التطوير", kindQuote: "الفلسفة والاقتباسات",
        kindGoal: "الأهداف", kindEducation: "التعليم", kindOpinion: "الآراء",
      },
      pillars: {
        intro: "يوجّه المزيج المستهدف ما يبحث عنه المساعد. يظهر الناتج الفعلي في شاشة الأداء، ويعدّل محرك التعلّم ضمن نطاق 0.7×–1.4× — ولا يسمح لأي محور بالهبوط إلى الصفر.",
        targetShare: "الحصة المستهدفة من مزيج محتواك",
      },
      topics: {
        tier: "المستوى {n}", tierHighest: " — أعلى وزن",
        addTopicPlaceholder: "مثال: البناء الأخضر، الهيدروجين…",
        excludedTitle: "مواضيع مستبعدة — لا تُعرض أبدًا",
        none: "لا يوجد شيء مستبعد.", excludePlaceholder: "مثال: السياسة", exclude: "استبعاد",
      },
      sources: {
        colSource: "المصدر", colRegion: "المنطقة", colCredibility: "المصداقية",
        colLastFetched: "آخر جلب", colEnabled: "مفعّل", never: "أبدًا",
      },
      social: {
        credentialsConfigured: "بيانات الاعتماد مضبوطة في بيئة الخادم.",
        addCredentials: "أضف بيانات الاعتماد إلى backend/.env للاتصال.",
      },
      publishing: {
        autoGreen: "النشر التلقائي للمحتوى الأخضر",
        lockedUntil: "مقفل حتى {date} — تبقى الأشهر الثلاثة الأولى يدوية بالكامل، وفقًا لسياسة الاعتماد الخاصة بك. لا يُنشر شيء دون مراجعتك قبل ذلك، بغض النظر عن مستوى الأمان.",
        unlockedNote: "انتهت الفترة اليدوية — يمكن الآن تفعيل هذا الخيار، لكنه يبقى معطّلاً حتى تفعّله صراحةً.",
        autoYellow: "النشر التلقائي للمحتوى الأصفر",
        yellowNote: "المحتوى الذي يحتوي رأيًا أو تنبؤًا يتطلب دائمًا موافقة يدوية، إلى أجل غير مسمى.",
        autoRed: "النشر التلقائي للمحتوى الأحمر",
        redNote: "غير متاح أبدًا — المحتوى الحساس أو غير الموثّق يتطلب دائمًا موافقة صريحة.",
      },
      approval: {
        pipelineEntry: "درجة دخول مسار المحتوى",
        pipelineEntryDesc: "أدنى درجة صلة لدخول قصة إلى مسار المحتوى أصلًا.",
        deepDive: "عتبة التغطية المعمّقة",
        deepDiveDesc: "الدرجة التي فوقها تستحق القصة مقالًا كاملًا أو سلسلة، لا مجرد منشور قصير.",
        duplicateSimilarity: "تشابه التكرار",
        duplicateSimilarityDesc: "تشابه العنوان فوق هذه النسبة يُعتبر “نفس القصة” — يمنع تعدد المنشورات حول حدث واحد.",
        minCredibility: "أدنى مصداقية للادعاءات الرقمية",
        minCredibilityDesc: "يحتاج الرقم المالي أو الإحصائي إلى مصداقية مصدر لا تقل عن هذه القيمة ليكون قابلاً للاستخدام.",
        factConfidenceAuto: "ثقة الحقيقة — مؤهّل للنشر التلقائي",
        factConfidenceAutoDesc: "دون هذه القيمة، يُحتجز المحتوى للمراجعة بغض النظر عن لون الأمان.",
        factConfidenceRed: "ثقة الحقيقة — يفرض التصنيف الأحمر",
        factConfidenceRedDesc: "دون هذه القيمة، يُصنَّف المحتوى تلقائيًا كأحمر.",
      },
      safety: {
        green: "أخضر", greenDesc: "معلومات عامة موثّقة أو محتوى تعليمي. مؤهّل للنشر التلقائي بعد انتهاء فترتك اليدوية البالغة 3 أشهر.",
        yellow: "أصفر", yellowDesc: "رأي أو تنبؤ أو تعليق تجاري. يتطلب دائمًا مراجعتك.",
        red: "أحمر", redDesc: "حساس، مالي، قانوني، شخصي، أو غير موثّق. لا يُنشر تلقائيًا أبدًا.",
        neverExpose: "لا يُذكر أبدًا، تحت أي ظرف",
        autoFlags: "يُصنَّف تلقائيًا كأحمر",
      },
      learning: {
        intro: "يفضّل النظام قليلًا المواضيع والصيغ التي تحقق أداءً جيدًا، ويقلّل قليلًا من التي لا تحققه — استنادًا إلى موافقاتك وتعديلاتك ورفضك وتفاعل المنشورات. لا يمكن دفع أي محور تحت حد 0.7× أو فوق 1.4× أبدًا.",
        currentMultiplier: "مُضاعِف التعلّم الحالي",
        recomputeNow: "إعادة الحساب الآن", recomputing: "جارٍ إعادة الحساب…",
      },
      system: {
        timezone: "المنطقة الزمنية", timezoneDesc: "تُستخدم لجدولة تفضيلات النشر",
        cadence: "وتيرة الاكتشاف", cadenceDesc: "عدد مرات فحص المصادر بحثًا عن قصص جديدة",
        defaultLang: "لغة المحتوى الافتراضية", defaultLangDesc: "العربية أولًا، والإنجليزية للزوايا الموجّهة عالميًا",
        environment: "البيئة", environmentDesc: "وضع النشر الذي يعمل عليه هذا الخادم",
      },
    },
    badges: {
      componentPersonalInterest: "الاهتمام الشخصي", componentBusinessRelevance: "الصلة بالأعمال",
      componentSaudiGcc: "الصلة بالسعودية / الخليج", componentStrategic: "الأهمية الاستراتيجية",
      componentAudienceValue: "قيمة الجمهور", componentFreshness: "الحداثة", componentCredibility: "مصداقية المصدر",
      total: "الإجمالي", noBreakdown: "لا يتوفر تفصيل للدرجة.",
      noSources: "لا مصادر خارجية — مأخوذ من المعرفة والحقائق الموثّقة.",
      safetyGreen: "موثّق / تعليمي", safetyYellow: "رأي / بحاجة لمراجعة", safetyRed: "خطورة عالية — يتطلب موافقة",
      confidenceHigh: "عالية", confidenceMedium: "متوسطة", confidenceLow: "منخفضة", confidenceSuffix: "الثقة",
    },
    pillars: {
      ai_technology: "الذكاء الاصطناعي والتقنية", entrepreneurship: "ريادة الأعمال",
      construction_engineering: "البناء والهندسة", real_estate: "التطوير العقاري",
      saudi_economy: "الاقتصاد السعودي ورؤية 2030", business_management: "إدارة الأعمال",
      investment: "الاستثمار", leadership_lessons: "القيادة والدروس المستفادة",
    },
  },
} as const;

function getPath(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => (o && typeof o === "object" ? (o as Record<string, unknown>)[k] : undefined), obj);
}

function interpolate(str: string, vars?: Record<string, string | number>): string {
  if (!vars) return str;
  return str.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
}

const LOCALE_COOKIE = "locale";

function readCookieLocale(): Locale | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|; )locale=(en|ar)/);
  return match ? (match[1] as Locale) : null;
}

function writeCookieLocale(locale: Locale) {
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; max-age=31536000; SameSite=Lax`;
}

interface LocaleContextValue {
  locale: Locale;
  dir: "ltr" | "rtl";
  setLocale: (l: Locale) => void;
  toggleLocale: () => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  pillarLabel: (key: string | null, fallback?: string) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children, initialLocale }: { children: React.ReactNode; initialLocale: Locale }) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);

  useEffect(() => {
    const fromCookie = readCookieLocale();
    if (fromCookie && fromCookie !== locale) setLocaleState(fromCookie);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = locale === "ar" ? "rtl" : "ltr";
  }, [locale]);

  function setLocale(l: Locale) {
    setLocaleState(l);
    writeCookieLocale(l);
  }
  function toggleLocale() {
    setLocale(locale === "en" ? "ar" : "en");
  }

  const value = useMemo<LocaleContextValue>(() => {
    const table: Record<string, unknown> = dict[locale];
    return {
      locale,
      dir: locale === "ar" ? "rtl" : "ltr",
      setLocale,
      toggleLocale,
      t: (key, vars) => {
        const raw = getPath(table, key);
        if (typeof raw !== "string") return key;
        return interpolate(raw, vars);
      },
      pillarLabel: (key, fallback) => {
        if (!key) return fallback || "";
        const raw = getPath(table.pillars, key);
        return typeof raw === "string" ? raw : (fallback || key);
      },
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}

export function getServerLocaleCookieName() {
  return LOCALE_COOKIE;
}
