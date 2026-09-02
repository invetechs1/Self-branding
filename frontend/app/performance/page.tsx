"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { PlatformBadge, PillarTag } from "@/components/Badges";
import { RefreshIcon, EmptyIcon } from "@/components/Icons";
import { api } from "@/lib/api";
import { PerformanceSummary, PublishedPost } from "@/lib/types";
import { useLocale } from "@/lib/i18n";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value mono">{value}</div>
    </div>
  );
}

export default function PerformancePage() {
  const { t, pillarLabel } = useLocale();
  const [summary, setSummary] = useState<PerformanceSummary | null>(null);
  const [posts, setPosts] = useState<PublishedPost[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recomputing, setRecomputing] = useState(false);

  function load() {
    api.performanceSummary().then((s) => setSummary(s as PerformanceSummary)).catch((e) => setError(String(e)));
    api.performancePosts().then((p) => setPosts(p as PublishedPost[])).catch((e) => setError(String(e)));
  }
  useEffect(load, []);

  async function handleRecompute() {
    setRecomputing(true);
    try {
      await api.recomputeLearning();
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setRecomputing(false);
    }
  }

  if (error) return <Shell wide><p style={{ color: "var(--danger)" }}>{t("performance.errorPrefix")}: {error}</p></Shell>;
  if (!summary || !posts) return <Shell wide><p style={{ color: "var(--muted)" }}>{t("performance.loading")}</p></Shell>;

  const topLearned = summary.learned[0];

  return (
    <Shell wide>
      <div className="grid-stats" style={{ marginBottom: 20 }}>
        <Stat label={t("performance.postsPublished")} value={String(summary.posts_published)} />
        <Stat label={t("performance.avgEngagement")}
              value={summary.posts_published ? `${(summary.avg_engagement_rate * 100).toFixed(1)}%` : "—"} />
        <Stat label={t("performance.approvalRate")}
              value={summary.approval_rate === null ? "—" : `${Math.round(summary.approval_rate * 100)}%`} />
        <Stat label={t("performance.totalImpressions")}
              value={summary.total_impressions ? `${(summary.total_impressions / 1000).toFixed(1)}k` : "0"} />
      </div>

      {topLearned && (
        <div className="card card-pad" style={{ marginBottom: 20, background: "var(--accent-soft)", borderColor: "var(--accent-soft-strong)" }}>
          <h3 style={{ fontSize: 15, color: "var(--accent)", marginBottom: 4 }}>{topLearned.label}</h3>
          <p style={{ fontSize: 13, color: "var(--ink)", opacity: 0.85 }}>{topLearned.text}</p>
        </div>
      )}

      <div className="grid-2" style={{ marginBottom: 20 }}>
        <div className="card card-pad">
          <h3 style={{ fontSize: 13.5, marginBottom: 10 }}>{t("performance.platformPerformance")}</h3>
          {summary.platform_performance.length === 0 ? (
            <p style={{ fontSize: 12.5, color: "var(--muted)" }}>{t("performance.noPublishedMeasured")}</p>
          ) : summary.platform_performance.map((p) => {
            const pct = Math.min(100, p.avg_engagement_rate * 1000);
            return (
              <div key={p.platform} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 0" }}>
                <PlatformBadge platform={p.platform} />
                <span style={{ width: 90, fontSize: 13 }}>{p.platform}</span>
                <div className="breakdown-track" style={{ flex: 1 }}>
                  <div className="breakdown-fill" style={{ width: `${pct}%` }} />
                </div>
                <span className="mono" style={{ width: 60, textAlign: "end" as const, fontSize: 12.5 }}>
                  {(p.avg_engagement_rate * 100).toFixed(1)}%
                </span>
              </div>
            );
          })}
        </div>
        <div className="card card-pad">
          <h3 style={{ fontSize: 13.5, marginBottom: 2 }}>{t("performance.whatLearned")}</h3>
          <p style={{ fontSize: 11.5, color: "var(--muted-2)", marginBottom: 2 }}>{t("performance.plainLanguage")}</p>
          {summary.learned.length === 0 ? (
            <p style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 8 }}>
              {t("performance.notEnoughData")}
            </p>
          ) : summary.learned.map((l) => (
            <div key={l.pillar} style={{ display: "flex", gap: 10, padding: "11px 0", borderBottom: "1px solid var(--border)" }}>
              <span style={{ color: "var(--accent)", flex: "none" }}>→</span>
              <p style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.55 }}><b style={{ color: "var(--ink)" }}>{l.label}:</b> {l.text}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card card-pad" style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 13.5, marginBottom: 2 }}>{t("performance.contentMix")}</h3>
        <p style={{ fontSize: 11.5, color: "var(--muted-2)", marginBottom: 6 }}>
          {t("performance.learningWeightNote")}
        </p>
        {summary.pillar_mix.map((p) => (
          <div key={p.key} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 0", borderBottom: "1px solid var(--border)" }}>
            <span style={{ flex: 1, fontSize: 13 }}>{pillarLabel(p.key, p.label)}</span>
            <span className="mono" style={{ fontSize: 11.5, color: "var(--muted-2)" }}>{t("performance.target", { pct: Math.round(p.target_share * 100) })}</span>
            <span className="mono" style={{ fontSize: 11.5, color: "var(--muted-2)" }}>{t("performance.actual", { pct: Math.round(p.actual_share * 100) })}</span>
            <span className={`pill ${p.multiplier > 1 ? "pill-success" : p.multiplier < 1 ? "pill-warning" : "pill-muted"}`}>
              ×{p.multiplier.toFixed(2)}
            </span>
          </div>
        ))}
        <div style={{ marginTop: 14 }}>
          <button className="btn btn-ghost" disabled={recomputing} onClick={handleRecompute}>
            <RefreshIcon /> {recomputing ? t("performance.recomputing") : t("performance.recomputeNow")}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-pad" style={{ paddingBottom: 6 }}><h3 style={{ fontSize: 13.5 }}>{t("performance.publishedPosts")}</h3></div>
        {posts.length === 0 ? (
          <div className="empty"><EmptyIcon /><h3>{t("performance.nothingPublished")}</h3><p>{t("performance.approveToSeePerf")}</p></div>
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead><tr><th></th><th>{t("performance.colPost")}</th><th>{t("performance.colDate")}</th><th>{t("performance.colImpressions")}</th><th>{t("performance.colLikes")}</th><th>{t("performance.colComments")}</th><th>{t("performance.colShares")}</th><th>{t("performance.colEngagement")}</th></tr></thead>
              <tbody>
                {posts.map((p) => (
                  <tr key={p.id}>
                    <td><PlatformBadge platform={p.platform} /></td>
                    <td>{p.hook}<div style={{ marginTop: 2 }}><PillarTag pillar={p.pillar} /></div></td>
                    <td className="mono">{p.posted_at ? new Date(p.posted_at).toLocaleDateString() : "—"}</td>
                    <td className="mono">{p.impressions !== null ? `${(p.impressions / 1000).toFixed(1)}k` : "—"}</td>
                    <td className="mono">{p.likes ?? "—"}</td>
                    <td className="mono">{p.comments ?? "—"}</td>
                    <td className="mono">{p.shares ?? "—"}</td>
                    <td className="mono">{p.engagement_rate !== null ? `${(p.engagement_rate * 100).toFixed(1)}%` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Shell>
  );
}
