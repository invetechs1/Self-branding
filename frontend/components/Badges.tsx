import { SafetyLevel } from "@/lib/types";
import { useLocale } from "@/lib/i18n";

// Relevance formula weights (docs/technical-requirements.md § 4 / profile/persona.yml
// -> relevance_weights) — used to render each score component as "v / max".
const COMPONENT_WEIGHTS: Record<string, number> = {
  personal_interest: 25, business_relevance: 20, saudi_gcc: 15, strategic: 15,
  audience_value: 10, freshness: 10, credibility: 5,
};
const COMPONENT_KEYS: Record<string, string> = {
  personal_interest: "badges.componentPersonalInterest", business_relevance: "badges.componentBusinessRelevance",
  saudi_gcc: "badges.componentSaudiGcc", strategic: "badges.componentStrategic",
  audience_value: "badges.componentAudienceValue", freshness: "badges.componentFreshness",
  credibility: "badges.componentCredibility",
};

export function ScoreBadge({ score }: { score: number | null }) {
  const s = score ?? 0;
  const cls = s >= 80 ? "" : s >= 60 ? "md" : "lo";
  return (
    <div className={`score-badge ${cls}`}>
      <b>{Math.round(s)}</b>
      <span>score</span>
    </div>
  );
}

export function SafetyPill({ level, withLabel = true }: { level: SafetyLevel; withLabel?: boolean }) {
  const { t } = useLocale();
  const map: Record<SafetyLevel, [string, string]> = {
    green: ["badges.safetyGreen", "success"],
    yellow: ["badges.safetyYellow", "warning"],
    red: ["badges.safetyRed", "danger"],
  };
  const [labelKey, cls] = map[level];
  return (
    <span className={`pill pill-${cls}`}>
      <span className={`safety-dot ${level}`} />
      {withLabel ? t(labelKey) : level.toUpperCase()}
    </span>
  );
}

export function ConfidencePill({ confidence }: { confidence: number | null }) {
  const { t } = useLocale();
  if (confidence === null) return null;
  const labelKey = confidence >= 0.8 ? "badges.confidenceHigh" : confidence >= 0.6 ? "badges.confidenceMedium" : "badges.confidenceLow";
  const cls = confidence >= 0.8 ? "success" : confidence >= 0.6 ? "warning" : "danger";
  return <span className={`pill pill-${cls}`}>{t(labelKey)} {t("badges.confidenceSuffix")}</span>;
}

export function PillarTag({ pillar }: { pillar: string | null }) {
  const { pillarLabel } = useLocale();
  if (!pillar) return null;
  return <span className="tag">{pillarLabel(pillar)}</span>;
}

export function PlatformBadge({ platform }: { platform: string }) {
  const label = platform === "x" || platform === "x_thread" ? "X" : platform === "linkedin_post" ? "in" : "IG";
  return <span className={`platform-badge ${platform}`}>{label}</span>;
}

export function BreakdownRows({ scores }: { scores: Record<string, number> | null }) {
  const { t } = useLocale();
  if (!scores) return <p style={{ color: "var(--muted)", fontSize: 12.5 }}>{t("badges.noBreakdown")}</p>;
  let total = 0, max = 0;
  const rows = Object.keys(COMPONENT_KEYS).map((key) => {
    const weight = COMPONENT_WEIGHTS[key];
    const value = Math.round((scores[key] ?? 0) * weight);
    total += value;
    max += weight;
    const pct = weight ? Math.round((value / weight) * 100) : 0;
    return (
      <div className="breakdown-row" key={key}>
        <span className="label">{t(COMPONENT_KEYS[key])}</span>
        <div className="breakdown-track"><div className="breakdown-fill" style={{ width: `${pct}%` }} /></div>
        <span className="val mono">{value}/{weight}</span>
      </div>
    );
  });
  return (
    <>
      {rows}
      <div className="breakdown-row" style={{ borderTop: "1px solid var(--border)", marginTop: 6, paddingTop: 8 }}>
        <span className="label" style={{ color: "var(--ink)", fontWeight: 600 }}>{t("badges.total")}</span>
        <div />
        <span className="val mono" style={{ fontWeight: 700, color: "var(--ink)" }}>{total}/{max}</span>
      </div>
    </>
  );
}

export function SourcesList({ sources }: { sources: { name: string; credibility: number }[] }) {
  const { t } = useLocale();
  if (!sources.length) {
    return <p style={{ color: "var(--muted)", fontSize: 12.5 }}>{t("badges.noSources")}</p>;
  }
  return (
    <>
      {sources.map((s, i) => {
        const cls = s.credibility >= 85 ? "" : s.credibility >= 60 ? "mid" : "low";
        return (
          <div className="source-row" key={i}>
            <span className={`cred-dot ${cls}`} />
            <span style={{ flex: 1 }}>{s.name}</span>
            <span className="mono" style={{ color: "var(--muted-2)", fontSize: 11.5 }}>{s.credibility}</span>
          </div>
        );
      })}
    </>
  );
}
