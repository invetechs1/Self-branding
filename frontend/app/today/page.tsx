"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/Shell";
import { ScoreBadge, PillarTag, ConfidencePill } from "@/components/Badges";
import { EmptyIcon, RefreshIcon } from "@/components/Icons";
import { api } from "@/lib/api";
import { ClusterOut, DiscoveryStatus } from "@/lib/types";
import { useLocale } from "@/lib/i18n";

function confidenceFromFactConfidence(fc: number | null): number | null {
  return fc;
}

export default function TodayPage() {
  const router = useRouter();
  const { t, locale, pillarLabel } = useLocale();

  function whyItMatters(c: ClusterOut): string {
    const pillar = pillarLabel(c.pillar, c.pillar || "");
    const region = c.region && c.region !== "global" ? t("today.inRegion", { region: c.region.replace("_", " ") }) : "";
    const sourceWord = c.source_count > 1 ? t("today.sourcePlural") : t("today.sourceSingular");
    return t("today.relevantTo", { pillar }) + region + t("today.corroborated", { count: c.source_count, sourceWord });
  }
  const [clusters, setClusters] = useState<ClusterOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [discovery, setDiscovery] = useState<DiscoveryStatus | null>(null);
  const [triggerError, setTriggerError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function loadClusters() {
    api.clusters().then((rows) => setClusters(rows as ClusterOut[])).catch((e) => setError(String(e)));
  }

  const pollStatus = useCallback(() => {
    api.discoveryStatus().then((s) => {
      const status = s as DiscoveryStatus;
      setDiscovery(status);
      if (status.status !== "running" && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        loadClusters();
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    loadClusters();
    api.discoveryStatus().then((s) => {
      const status = s as DiscoveryStatus;
      setDiscovery(status);
      if (status.status === "running") {
        pollRef.current = setInterval(pollStatus, 3000);
      }
    }).catch(() => {});
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [pollStatus]);

  async function handleFetchLatest() {
    setTriggerError(null);
    try {
      await api.triggerDiscovery();
      setDiscovery((prev) => prev ? { ...prev, status: "running" } : prev);
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(pollStatus, 3000);
    } catch (e) {
      setTriggerError(String(e));
    }
  }

  const isRunning = discovery?.status === "running";
  const hour = new Date().getHours();
  const greet = hour < 12 ? t("today.greetMorning") : hour < 18 ? t("today.greetAfternoon") : t("today.greetEvening");

  const stats = [
    [t("today.statsAnalyzed"), clusters?.length ?? "—"],
    [t("today.statsAttention"), clusters ? Math.min(clusters.length, 10) : "—"],
  ] as const;

  return (
    <Shell>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 14, marginBottom: 2 }}>
        <div>
          <h2 style={{ fontSize: 20, marginBottom: 2 }}>{greet}, Yahya.</h2>
          <p style={{ color: "var(--muted)" }}>{t("today.subtitle")}</p>
        </div>
        <button className="btn btn-primary" disabled={isRunning} onClick={handleFetchLatest} style={{ flex: "none", marginTop: 2 }}>
          {isRunning ? (<><span className="spinner" /> {t("today.fetching")}</>) : (<><RefreshIcon /> {t("today.fetchLatest")}</>)}
        </button>
      </div>

      {isRunning && (
        <p style={{ fontSize: 12.5, color: "var(--muted-2)", margin: "10px 0" }}>
          {t("today.checkingSources")}
        </p>
      )}
      {!isRunning && discovery?.completed_at && discovery.last_result && (
        <p style={{ fontSize: 12.5, color: "var(--muted-2)", margin: "10px 0" }}>
          {t("today.lastFetch", {
            kept: discovery.last_result.kept,
            storyWord: discovery.last_result.kept === 1 ? t("today.storySingular") : t("today.storyPlural"),
            fetched: discovery.last_result.fetched,
            time: new Date(discovery.completed_at).toLocaleTimeString(locale === "ar" ? "ar-SA" : "en-US"),
          })}
        </p>
      )}
      {!isRunning && discovery?.status === "error" && (
        <p style={{ fontSize: 12.5, color: "var(--danger)", margin: "10px 0" }}>
          {t("today.lastFetchFailed", { error: discovery.error || "" })}
        </p>
      )}
      {triggerError && <p style={{ fontSize: 12.5, color: "var(--danger)", margin: "10px 0" }}>{triggerError}</p>}

      <div className="grid-stats" style={{ marginBottom: 22, marginTop: 16, gridTemplateColumns: "repeat(2, 1fr)", maxWidth: 480 }}>
        {stats.map(([label, value]) => (
          <div className="stat-card" key={label}>
            <div className="stat-label">{label}</div>
            <div className="stat-value mono">{value}</div>
          </div>
        ))}
      </div>

      {error && <p style={{ color: "var(--danger)" }}>{t("opportunities.errorPrefix")}: {error}</p>}
      {!clusters && !error && <p style={{ color: "var(--muted)" }}>{t("common.loading")}</p>}
      {clusters && clusters.length === 0 && (
        <div className="empty">
          <EmptyIcon />
          <h3>{t("today.emptyTitle")}</h3>
          <p>{t("today.emptyBody")}</p>
        </div>
      )}

      {clusters?.map((c) => (
        <div className="story-card" key={c.id}>
          <ScoreBadge score={c.relevance} />
          <div className="story-main">
            <div className="story-title">{c.headline}</div>
            <div className="story-meta">
              <PillarTag pillar={c.pillar} />
              {c.region && <span className="tag">{c.region}</span>}
            </div>
            <div className="story-why">{whyItMatters(c)}</div>
            <div className="story-foot">
              <span className="src-note">
                {c.source_count} {c.source_count > 1 ? t("today.sourcePlural") : t("today.sourceSingular")} ·{" "}
                <ConfidencePill confidence={confidenceFromFactConfidence(c.fact_confidence)} />
              </span>
              {c.freshness && <span className="src-note mono" style={{ marginInlineStart: 8 }}>{c.freshness}</span>}
              <div className="story-actions">
                <button className="btn btn-ghost btn-sm" onClick={() => router.push(`/opportunities`)}>
                  {t("today.viewInOpportunities")}
                </button>
              </div>
            </div>
          </div>
        </div>
      ))}
    </Shell>
  );
}
