"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/Shell";
import { ScoreBadge, PillarTag, ConfidencePill } from "@/components/Badges";
import { EmptyIcon, OpportunitiesIcon } from "@/components/Icons";
import { api } from "@/lib/api";
import { OpportunityOut } from "@/lib/types";
import { useLocale } from "@/lib/i18n";

export default function OpportunitiesPage() {
  const router = useRouter();
  const { t } = useLocale();
  const PLATFORMS = [
    { value: "linkedin_post", label: t("opportunities.platformLinkedin") },
    { value: "x", label: t("opportunities.platformX") },
    { value: "x_thread", label: t("opportunities.platformXThread") },
  ];
  const TYPE_LABELS: Record<string, string> = {
    bassir_feature: t("opportunities.typeBassirFeature"), partnership: t("opportunities.typePartnership"),
    investment_theme: t("opportunities.typeInvestmentTheme"), competitive_intel: t("opportunities.typeCompetitiveIntel"),
  };
  const [opps, setOpps] = useState<OpportunityOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [platformByOpp, setPlatformByOpp] = useState<Record<string, string>>({});
  const [generatingId, setGeneratingId] = useState<string | null>(null);

  function load() {
    api.opportunities().then((rows) => setOpps(rows as OpportunityOut[])).catch((e) => setError(String(e)));
  }
  useEffect(load, []);

  async function handleCreateDraft(o: OpportunityOut) {
    const platform = platformByOpp[o.id] || "linkedin_post";
    setGeneratingId(o.id);
    try {
      const draft: any = await api.generateDraft(o.cluster_id, platform);
      router.push(`/drafts?id=${draft.id}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setGeneratingId(null);
    }
  }

  async function handleDismiss(o: OpportunityOut) {
    await api.dismissOpportunity(o.id);
    setOpps((prev) => (prev ? prev.filter((x) => x.id !== o.id) : prev));
  }

  return (
    <Shell>
      {error && <p style={{ color: "var(--danger)", marginBottom: 16 }}>{t("opportunities.errorPrefix")}: {error}</p>}
      {!opps && !error && <p style={{ color: "var(--muted)" }}>{t("opportunities.loading")}</p>}
      {opps && opps.length === 0 && (
        <div className="empty">
          <EmptyIcon />
          <h3>{t("opportunities.emptyTitle")}</h3>
          <p>{t("opportunities.emptyBody")}</p>
        </div>
      )}

      {opps?.map((o) => (
        <div className="card card-pad" style={{ marginBottom: 12 }} key={o.id}>
          <div style={{ display: "flex", gap: 14 }}>
            <ScoreBadge score={o.relevance} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10, justifyContent: "space-between" }}>
                <h3 style={{ fontSize: 15, lineHeight: 1.4 }}>{o.headline}</h3>
                <span className="pill pill-accent">{TYPE_LABELS[o.opportunity_type] || o.opportunity_type}</span>
              </div>
              <div className="story-meta" style={{ margin: "8px 0" }}>
                <PillarTag pillar={o.pillar} />
                {o.region && <span className="tag">{o.region}</span>}
              </div>
              <p style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.55 }}>
                <b style={{ color: "var(--ink)" }}>{t("opportunities.labelPrefix")}</b> {o.label}
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
                <span className="src-note">
                  {o.source_count} {o.source_count > 1 ? t("opportunities.sourcePlural") : t("opportunities.sourceSingular")} ·{" "}
                  <ConfidencePill confidence={o.fact_confidence} />
                </span>
                <div style={{ marginInlineStart: "auto", display: "flex", gap: 8, alignItems: "center" }}>
                  <select
                    className="input"
                    style={{ width: "auto" }}
                    value={platformByOpp[o.id] || "linkedin_post"}
                    onChange={(e) => setPlatformByOpp((prev) => ({ ...prev, [o.id]: e.target.value }))}
                  >
                    {PLATFORMS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                  </select>
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={generatingId === o.id}
                    onClick={() => handleCreateDraft(o)}
                  >
                    {generatingId === o.id ? (<><span className="spinner" /> {t("opportunities.generating")}</>) : t("opportunities.createDraft")}
                  </button>
                  <button className="btn btn-ghost btn-icon" title={t("opportunities.dismiss")} onClick={() => handleDismiss(o)}>
                    ✕
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ))}
    </Shell>
  );
}
