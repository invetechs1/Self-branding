"use client";

import { Fragment, useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";
import {
  InterestOut, KnowledgeItem, PillarSetting, ProfileOut, PublishingRules,
  SourceSetting, TopicsOut,
} from "@/lib/types";
import { RefreshIcon } from "@/components/Icons";
import { useLocale } from "@/lib/i18n";

const SECTION_KEYS = [
  "profile", "knowledge", "pillars", "topics", "sources", "social",
  "publishing", "approval", "safety", "learning", "system",
] as const;
type SectionKey = (typeof SECTION_KEYS)[number];

export default function SettingsPage() {
  const { t } = useLocale();
  const [section, setSection] = useState<SectionKey>("profile");

  return (
    <Shell wide>
      <div className="settings-shell">
        <div className="settings-nav">
          {SECTION_KEYS.map((key) => (
            <button key={key} className={section === key ? "active" : ""} onClick={() => setSection(key)}>
              {t(`settings.sections.${key}`)}
            </button>
          ))}
        </div>
        <div className="settings-panel">
          {section === "profile" && <ProfileSection />}
          {section === "knowledge" && <KnowledgeSection />}
          {section === "pillars" && <PillarsSection />}
          {section === "topics" && <TopicsSection />}
          {section === "sources" && <SourcesSection />}
          {section === "social" && <SocialSection />}
          {section === "publishing" && <PublishingSection />}
          {section === "approval" && <ApprovalSection />}
          {section === "safety" && <SafetySection />}
          {section === "learning" && <LearningSection />}
          {section === "system" && <SystemSection />}
        </div>
      </div>
    </Shell>
  );
}

function Loading() {
  const { t } = useLocale();
  return <p style={{ color: "var(--muted)" }}>{t("common.loading")}</p>;
}
function ErrorText({ message }: { message: string }) {
  const { t } = useLocale();
  return <p style={{ color: "var(--danger)" }}>{t("common.error")}: {message}</p>;
}

// ── Profile ──

function ProfileSection() {
  const { t } = useLocale();
  const [profile, setProfile] = useState<ProfileOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.profile().then((p) => setProfile(p as ProfileOut)).catch((e) => setError(String(e)));
  }, []);

  if (error) return <ErrorText message={error} />;
  if (!profile) return <Loading />;

  const accounts = [
    ["x", "X (Twitter)"], ["linkedin", "LinkedIn"], ["instagram", "Instagram"],
  ] as const;

  return (
    <div className="card card-pad">
      <div className="field-wrap"><label className="field">{t("settings.profile.nameAr")}</label>
        <input className="input rtl" value={profile.name_ar} readOnly /></div>
      <div className="field-wrap"><label className="field">{t("settings.profile.nameEn")}</label>
        <input className="input" value={profile.name_en} readOnly /></div>
      <div className="field-wrap"><label className="field">{t("settings.profile.headline")}</label>
        <input className="input" value={profile.headline || ""} readOnly /></div>
      <div className="field-wrap"><label className="field">{t("settings.profile.city")}</label>
        <input className="input" value={profile.city || ""} placeholder={t("settings.profile.notAdded")} readOnly />
        <div className="field-hint">{t("settings.profile.cityHint")}</div>
      </div>
      <div className="section-title">{t("settings.profile.socialHandles")}</div>
      {accounts.map(([key, label]) => {
        const acc = profile.accounts[key];
        return (
          <div className="settings-row" key={key}>
            <div className="meta"><b>{label}</b><span>{acc.note || (acc.connected ? t("settings.profile.connected") : t("settings.profile.notConnected"))}</span></div>
            <span className={`pill ${acc.connected ? "pill-success" : "pill-muted"}`}>
              {acc.connected ? t("settings.profile.connected") : t("settings.profile.notConnected")}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Knowledge / Facts ──

function KnowledgeSection() {
  const { t } = useLocale();
  const KIND_LABELS: Record<string, string> = {
    bio: t("settings.knowledge.kindBio"), project: t("settings.knowledge.kindProject"),
    company: t("settings.knowledge.kindCompany"), product: t("settings.knowledge.kindProduct"),
    quote: t("settings.knowledge.kindQuote"), goal: t("settings.knowledge.kindGoal"),
    education: t("settings.knowledge.kindEducation"), opinion: t("settings.knowledge.kindOpinion"),
  };
  const [items, setItems] = useState<KnowledgeItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newBody, setNewBody] = useState("");

  function load() {
    api.knowledge().then((rows) => setItems(rows as KnowledgeItem[])).catch((e) => setError(String(e)));
  }
  useEffect(load, []);

  async function togglePublic(item: KnowledgeItem) {
    await api.updateKnowledge(item.id, { is_public: !item.is_public });
    load();
  }

  async function handleAdd() {
    if (!newTitle.trim() || !newBody.trim()) return;
    await api.addKnowledge("opinion", newTitle, newBody, true);
    setNewTitle(""); setNewBody(""); setAdding(false);
    load();
  }

  if (error) return <ErrorText message={error} />;
  if (!items) return <Loading />;

  const groups: Record<string, KnowledgeItem[]> = {};
  for (const item of items) (groups[item.kind] ||= []).push(item);

  return (
    <div>
      <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 16 }}>
        {t("settings.knowledge.intro")}
      </p>
      {Object.entries(groups).map(([kind, rows]) => (
        <Fragment key={kind}>
          <div className="section-title">{KIND_LABELS[kind] || kind}</div>
          <div className="card card-rows">
            {rows.map((k) => (
              <div className="settings-row" key={k.id}>
                <div className="meta"><b>{k.title}</b><span>{k.body.length > 140 ? k.body.slice(0, 140) + "…" : k.body}</span></div>
                <span className={`pill ${k.is_public ? "pill-success" : "pill-muted"}`} style={{ cursor: "pointer" }}
                      onClick={() => togglePublic(k)}>
                  {k.is_public ? t("settings.knowledge.public") : t("settings.knowledge.private")}
                </span>
              </div>
            ))}
          </div>
        </Fragment>
      ))}
      {adding ? (
        <div className="card card-pad" style={{ marginTop: 16 }}>
          <div className="field-wrap"><label className="field">{t("settings.knowledge.title")}</label>
            <input className="input" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} /></div>
          <div className="field-wrap"><label className="field">{t("settings.knowledge.body")}</label>
            <textarea className="textarea" value={newBody} onChange={(e) => setNewBody(e.target.value)} /></div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary btn-sm" onClick={handleAdd}>{t("common.save")}</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setAdding(false)}>{t("common.cancel")}</button>
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 16 }}>
          <button className="btn btn-ghost" onClick={() => setAdding(true)}>{t("settings.knowledge.addFact")}</button>
        </div>
      )}
    </div>
  );
}

// ── Content Pillars ──

function PillarsSection() {
  const { t, locale } = useLocale();
  const [pillars, setPillars] = useState<PillarSetting[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api.pillarSettings().then((rows) => setPillars(rows as PillarSetting[])).catch((e) => setError(String(e)));
  }
  useEffect(load, []);

  async function handleChange(key: string, value: number) {
    setPillars((prev) => prev ? prev.map((p) => p.key === key ? { ...p, target_share: value } : p) : prev);
  }
  async function handleCommit(key: string, value: number) {
    await api.updatePillarShare(key, value);
  }

  if (error) return <ErrorText message={error} />;
  if (!pillars) return <Loading />;

  return (
    <>
      <div className="card card-pad">
        <p style={{ fontSize: 13, color: "var(--muted)" }}>
          {t("settings.pillars.intro")}
        </p>
      </div>
      <div className="card card-rows" style={{ marginTop: 14 }}>
        {pillars.map((p) => (
          <div className="settings-row" key={p.key}>
            <div className="meta"><b>{locale === "ar" ? p.label_ar : p.label_en}</b><span>{t("settings.pillars.targetShare")}</span></div>
            <input type="range" min={0} max={40} value={Math.round(p.target_share * 100)}
                   className="range-input"
                   onChange={(e) => handleChange(p.key, Number(e.target.value) / 100)}
                   onMouseUp={(e) => handleCommit(p.key, Number((e.target as HTMLInputElement).value) / 100)} />
            <span className="mono" style={{ width: 40, textAlign: "end" as const }}>{Math.round(p.target_share * 100)}%</span>
          </div>
        ))}
      </div>
    </>
  );
}

// ── Topics ──

function TopicsSection() {
  const { t } = useLocale();
  const [topics, setTopics] = useState<TopicsOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newTopic, setNewTopic] = useState("");
  const [newExcluded, setNewExcluded] = useState("");

  function load() {
    api.topics().then((t) => setTopics(t as TopicsOut)).catch((e) => setError(String(e)));
  }
  useEffect(load, []);

  async function handleAddTopic() {
    if (!newTopic.trim()) return;
    await api.addTopic(newTopic.trim());
    setNewTopic("");
    load();
  }
  async function handleRemoveTopic(id: number) {
    await api.removeTopic(id);
    load();
  }
  async function handleAddExcluded() {
    if (!newExcluded.trim()) return;
    await api.addExcludedTopic(newExcluded.trim());
    setNewExcluded("");
    load();
  }
  async function handleRemoveExcluded(topic: string) {
    await api.removeExcludedTopic(topic);
    load();
  }

  if (error) return <ErrorText message={error} />;
  if (!topics) return <Loading />;

  const tiers: Record<number, InterestOut[]> = {};
  for (const t of topics.tracked) (tiers[t.tier] ||= []).push(t);

  return (
    <div>
      {[1, 2, 3].map((tier) => tiers[tier] && (
        <Fragment key={tier}>
          <div className="section-title">{t("settings.topics.tier", { n: tier })}{tier === 1 ? t("settings.topics.tierHighest") : ""}</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
            {tiers[tier].map((topic) => (
              <span className="chip selected" key={topic.id}>
                {topic.name} <span className="x" style={{ cursor: "pointer" }} onClick={() => handleRemoveTopic(topic.id)}>×</span>
              </span>
            ))}
          </div>
        </Fragment>
      ))}
      <div className="field-wrap" style={{ marginTop: 14, maxWidth: 320, display: "flex", gap: 8 }}>
        <input className="input" placeholder={t("settings.topics.addTopicPlaceholder")} value={newTopic}
               onChange={(e) => setNewTopic(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && handleAddTopic()} />
        <button className="btn btn-sm btn-primary" onClick={handleAddTopic}>{t("common.add")}</button>
      </div>

      <div className="section-title">{t("settings.topics.excludedTitle")}</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        {topics.excluded.length === 0 && <p style={{ fontSize: 12.5, color: "var(--muted)" }}>{t("settings.topics.none")}</p>}
        {topics.excluded.map((topic) => (
          <span key={topic} className="chip" style={{ background: "var(--danger-soft)", borderColor: "transparent", color: "var(--danger)", cursor: "pointer" }}
                onClick={() => handleRemoveExcluded(topic)}>
            {topic} ×
          </span>
        ))}
      </div>
      <div className="field-wrap" style={{ maxWidth: 320, display: "flex", gap: 8 }}>
        <input className="input" placeholder={t("settings.topics.excludePlaceholder")} value={newExcluded}
               onChange={(e) => setNewExcluded(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && handleAddExcluded()} />
        <button className="btn btn-sm btn-danger" onClick={handleAddExcluded}>{t("settings.topics.exclude")}</button>
      </div>
    </div>
  );
}

// ── Sources ──

function SourcesSection() {
  const { t } = useLocale();
  const [sources, setSources] = useState<SourceSetting[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api.sourceSettings().then((rows) => setSources(rows as SourceSetting[])).catch((e) => setError(String(e)));
  }
  useEffect(load, []);

  async function handleToggle(id: number) {
    await api.toggleSource(id);
    load();
  }

  if (error) return <ErrorText message={error} />;
  if (!sources) return <Loading />;

  return (
    <div className="card">
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>{t("settings.sources.colSource")}</th><th>{t("settings.sources.colRegion")}</th><th>{t("settings.sources.colCredibility")}</th><th>{t("settings.sources.colLastFetched")}</th><th>{t("settings.sources.colEnabled")}</th></tr></thead>
          <tbody>
            {sources.map((s) => {
              const cls = s.credibility >= 85 ? "" : s.credibility >= 60 ? "mid" : "low";
              return (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.region || "—"}</td>
                  <td><span className={`cred-dot ${cls}`} /> {s.credibility}</td>
                  <td className="mono" style={{ color: "var(--muted-2)" }}>
                    {s.last_fetched_at ? new Date(s.last_fetched_at).toLocaleString() : t("settings.sources.never")}
                  </td>
                  <td><div className={`switch ${s.enabled ? "on" : ""}`} style={{ cursor: "pointer" }}
                           onClick={() => handleToggle(s.id)} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Social Accounts ──

function SocialSection() {
  const { t } = useLocale();
  const [profile, setProfile] = useState<ProfileOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.profile().then((p) => setProfile(p as ProfileOut)).catch((e) => setError(String(e)));
  }, []);

  if (error) return <ErrorText message={error} />;
  if (!profile) return <Loading />;

  const cards = [
    ["x", "X (Twitter)"], ["linkedin", "LinkedIn"], ["instagram", "Instagram"],
  ] as const;

  return (
    <div className="grid-2">
      {cards.map(([key, label]) => {
        const acc = profile.accounts[key];
        return (
          <div className="card card-pad" key={key}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
              <b style={{ fontSize: 14 }}>{label}</b>
              <span className={`pill ${acc.connected ? "pill-success" : "pill-muted"}`} style={{ marginInlineStart: "auto" }}>
                {acc.connected ? t("settings.profile.connected") : t("settings.profile.notConnected")}
              </span>
            </div>
            <p style={{ fontSize: 12, color: "var(--muted-2)" }}>
              {acc.note || (acc.connected ? t("settings.social.credentialsConfigured") : t("settings.social.addCredentials"))}
            </p>
          </div>
        );
      })}
    </div>
  );
}

// ── Publishing Rules ──

function PublishingSection() {
  const { t } = useLocale();
  const [rules, setRules] = useState<PublishingRules | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.publishingRules().then((r) => setRules(r as PublishingRules)).catch((e) => setError(String(e)));
  }, []);

  if (error) return <ErrorText message={error} />;
  if (!rules) return <Loading />;

  return (
    <div className="card card-pad">
      <div className="settings-row">
        <div className="meta"><b>{t("settings.publishing.autoGreen")}</b>
          <span>
            {rules.manual_period_locked
              ? t("settings.publishing.lockedUntil", { date: rules.manual_period_ends })
              : t("settings.publishing.unlockedNote")}
          </span>
        </div>
        <div className={`switch ${rules.auto_publish_green ? "on" : ""} ${rules.manual_period_locked ? "locked" : ""}`} />
      </div>
      <div className="settings-row">
        <div className="meta"><b>{t("settings.publishing.autoYellow")}</b><span>{t("settings.publishing.yellowNote")}</span></div>
        <div className="switch locked" />
      </div>
      <div className="settings-row">
        <div className="meta"><b>{t("settings.publishing.autoRed")}</b><span>{t("settings.publishing.redNote")}</span></div>
        <div className="switch locked" />
      </div>
    </div>
  );
}

// ── Approval Rules ──

function ApprovalSection() {
  const { t } = useLocale();
  const [thresholds, setThresholds] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.approvalThresholds().then((th) => setThresholds(th as Record<string, number>)).catch((e) => setError(String(e)));
  }, []);

  if (error) return <ErrorText message={error} />;
  if (!thresholds) return <Loading />;

  const rows: [string, string, string][] = [
    ["pipeline_entry", "pipelineEntry", "pipelineEntryDesc"],
    ["deep_dive", "deepDive", "deepDiveDesc"],
    ["duplicate_similarity", "duplicateSimilarity", "duplicateSimilarityDesc"],
    ["min_credibility_for_facts", "minCredibility", "minCredibilityDesc"],
    ["fact_confidence_autopublish", "factConfidenceAuto", "factConfidenceAutoDesc"],
    ["fact_confidence_red", "factConfidenceRed", "factConfidenceRedDesc"],
  ];

  return (
    <div className="card card-rows">
      {rows.map(([key, labelKey, descKey]) => (
        <div className="settings-row" key={key}>
          <div className="meta"><b>{t(`settings.approval.${labelKey}`)}</b><span>{t(`settings.approval.${descKey}`)}</span></div>
          <span className="pill pill-accent mono">{thresholds[key] ?? "—"}</span>
        </div>
      ))}
    </div>
  );
}

// ── Safety ──

function SafetySection() {
  const { t } = useLocale();
  const [safety, setSafety] = useState<{ never_expose: string[]; red_flag_terms: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.safetyConfig().then((s) => setSafety(s as any)).catch((e) => setError(String(e)));
  }, []);

  if (error) return <ErrorText message={error} />;
  if (!safety) return <Loading />;

  return (
    <div>
      <div className="grid-2" style={{ marginBottom: 16 }}>
        <div className="card card-pad">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}><span className="safety-dot green" /><b>{t("settings.safety.green")}</b></div>
          <p style={{ fontSize: 12.5, color: "var(--muted)" }}>{t("settings.safety.greenDesc")}</p>
        </div>
        <div className="card card-pad">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}><span className="safety-dot yellow" /><b>{t("settings.safety.yellow")}</b></div>
          <p style={{ fontSize: 12.5, color: "var(--muted)" }}>{t("settings.safety.yellowDesc")}</p>
        </div>
        <div className="card card-pad">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}><span className="safety-dot red" /><b>{t("settings.safety.red")}</b></div>
          <p style={{ fontSize: 12.5, color: "var(--muted)" }}>{t("settings.safety.redDesc")}</p>
        </div>
      </div>
      <div className="section-title">{t("settings.safety.neverExpose")}</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {safety.never_expose.map((item) => <span className="tag" key={item}>{item}</span>)}
      </div>
      <div className="section-title">{t("settings.safety.autoFlags")}</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {safety.red_flag_terms.map((item) => <span className="tag mono" key={item}>{item}</span>)}
      </div>
    </div>
  );
}

// ── Learning ──

function LearningSection() {
  const { t, locale } = useLocale();
  const [pillars, setPillars] = useState<PillarSetting[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recomputing, setRecomputing] = useState(false);

  function load() {
    api.pillarSettings().then((rows) => setPillars(rows as PillarSetting[])).catch((e) => setError(String(e)));
  }
  useEffect(load, []);

  async function handleRecompute() {
    setRecomputing(true);
    try { await api.recomputeLearning(); load(); }
    catch (e) { setError(String(e)); }
    finally { setRecomputing(false); }
  }

  if (error) return <ErrorText message={error} />;
  if (!pillars) return <Loading />;

  return (
    <div>
      <div className="card card-pad" style={{ marginBottom: 14 }}>
        <p style={{ fontSize: 13, color: "var(--muted)" }}>
          {t("settings.learning.intro")}
        </p>
      </div>
      <div className="card card-rows">
        {pillars.map((p) => (
          <div className="settings-row" key={p.key}>
            <div className="meta"><b>{locale === "ar" ? p.label_ar : p.label_en}</b><span>{t("settings.learning.currentMultiplier")}</span></div>
            <span className={`pill ${p.multiplier > 1 ? "pill-success" : p.multiplier < 1 ? "pill-warning" : "pill-muted"} mono`}>
              ×{p.multiplier.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 14 }}>
        <button className="btn btn-ghost" disabled={recomputing} onClick={handleRecompute}>
          <RefreshIcon /> {recomputing ? t("settings.learning.recomputing") : t("settings.learning.recomputeNow")}
        </button>
      </div>
    </div>
  );
}

// ── System ──

function SystemSection() {
  const { t, locale } = useLocale();
  const [config, setConfig] = useState<Record<string, string> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.systemConfig().then((c) => setConfig(c as Record<string, string>)).catch((e) => setError(String(e)));
  }, []);

  if (error) return <ErrorText message={error} />;
  if (!config) return <Loading />;

  return (
    <div className="card card-pad">
      <div className="settings-row"><div className="meta"><b>{t("settings.system.timezone")}</b><span>{t("settings.system.timezoneDesc")}</span></div>
        <span className="pill pill-muted mono">{config.timezone}</span></div>
      <div className="settings-row"><div className="meta"><b>{t("settings.system.cadence")}</b><span>{t("settings.system.cadenceDesc")}</span></div>
        <span className="pill pill-muted mono">{config.discovery_cadence}</span></div>
      <div className="settings-row"><div className="meta"><b>{t("settings.system.defaultLang")}</b><span>{t("settings.system.defaultLangDesc")}</span></div>
        <span className="pill pill-muted">{config.default_language === "ar" ? (locale === "ar" ? "العربية (ar)" : "Arabic (ar)") : (locale === "ar" ? "الإنجليزية (en)" : "English (en)")}</span></div>
      <div className="settings-row"><div className="meta"><b>{t("settings.system.environment")}</b><span>{t("settings.system.environmentDesc")}</span></div>
        <span className={`pill ${config.environment === "production" ? "pill-success" : "pill-warning"}`}>{config.environment}</span></div>
    </div>
  );
}
