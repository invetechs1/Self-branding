"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Shell } from "@/components/Shell";
import { ScoreBadge, PillarTag, ConfidencePill, PlatformBadge, BreakdownRows, SourcesList } from "@/components/Badges";
import { DraftsIcon, RefreshIcon } from "@/components/Icons";
import { api } from "@/lib/api";
import { DraftOut } from "@/lib/types";
import { useLocale } from "@/lib/i18n";

const REASON_TAGS = ["tone", "inaccurate", "off-brand", "repetitive", "sensitive", "weak-insight"];

export default function DraftsPage() {
  return (
    <Suspense fallback={null}>
      <DraftsPageInner />
    </Suspense>
  );
}

function DraftsPageInner() {
  const { t } = useLocale();
  const FILTERS = [
    ["all", t("drafts.filterAll")], ["needs-review", t("drafts.filterNeedsReview")], ["linkedin_post", t("drafts.filterLinkedin")],
    ["x", t("drafts.filterX")], ["red", t("drafts.filterRed")],
  ] as const;

  function reasonBanner(d: DraftOut) {
    const cls = d.approval_level;
    const text = d.review_notes || (cls === "green"
      ? t("drafts.reasonGreen") : cls === "yellow" ? t("drafts.reasonYellow") : t("drafts.reasonRed"));
    const label = cls === "red" ? t("drafts.labelRed") : cls === "yellow" ? t("drafts.labelYellow") : t("drafts.labelVerified");
    const dot = cls === "red" ? "🔴" : cls === "yellow" ? "🟡" : "🟢";
    return (
      <div className={`reason-banner ${cls}`}>
        <strong style={{ flex: "none" }}>{dot}</strong>
        <div><b>{label}</b><br />{text}</div>
      </div>
    );
  }

  const searchParams = useSearchParams();
  const [drafts, setDrafts] = useState<DraftOut[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("id"));
  const [filter, setFilter] = useState<string>("all");
  const [editing, setEditing] = useState(false);
  const [editBody, setEditBody] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [selectedReasons, setSelectedReasons] = useState<string[]>([]);
  const [confirmingRed, setConfirmingRed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const railRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    api.drafts().then((rows) => {
      const list = rows as DraftOut[];
      setDrafts(list);
      setSelectedId((prev) => prev && list.some((d) => d.id === prev) ? prev
        : (list.find((d) => d.status === "pending_review") || list[0])?.id || null);
    }).catch((e) => setError(String(e)));
  }, []);
  useEffect(load, [load]);

  const filtered = useMemo(() => {
    if (!drafts) return [];
    if (filter === "all") return drafts;
    if (filter === "needs-review") return drafts.filter((d) => d.status === "pending_review");
    if (filter === "red") return drafts.filter((d) => d.approval_level === "red");
    return drafts.filter((d) => d.platform === filter);
  }, [drafts, filter]);

  const selected = drafts?.find((d) => d.id === selectedId) || null;
  const total = drafts?.length ?? 0;
  const reviewed = drafts?.filter((d) => d.status !== "pending_review").length ?? 0;
  const pct = total ? Math.round((reviewed / total) * 100) : 0;

  function selectNext() {
    const pool = filtered.length ? filtered : (drafts || []);
    const idx = pool.findIndex((d) => d.id === selectedId);
    const next = pool.slice(idx + 1).find((d) => d.status === "pending_review")
      || pool.find((d) => d.status === "pending_review" && d.id !== selectedId);
    setSelectedId(next ? next.id : null);
    setEditing(false); setRejecting(false); setConfirmingRed(false);
  }

  async function handleApprove(confirmedRed = false) {
    if (!selected) return;
    if (selected.approval_level === "red" && !confirmedRed) { setConfirmingRed(true); return; }
    setBusy(true);
    try {
      await api.approveDraft(selected.id, confirmedRed);
      await refreshAndAdvance();
    } catch (e) { setError(String(e)); } finally { setBusy(false); setConfirmingRed(false); }
  }

  async function handleSaveApprove() {
    if (!selected) return;
    setBusy(true);
    try {
      await api.editApproveDraft(selected.id, editBody, selected.approval_level === "red");
      setEditing(false);
      await refreshAndAdvance();
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }

  async function handleReject() {
    if (!selected) return;
    setBusy(true);
    try {
      await api.rejectDraft(selected.id, selectedReasons);
      setRejecting(false); setSelectedReasons([]);
      await refreshAndAdvance();
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }

  async function handleRegenerate() {
    if (!selected) return;
    setBusy(true);
    try {
      const fresh: any = await api.regenerateDraft(selected.id, "full");
      load();
      setSelectedId(fresh.id);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }

  async function handlePublish() {
    if (!selected) return;
    setBusy(true);
    try {
      const updated: any = await api.publishDraft(selected.id);
      setDrafts((prev) => prev ? prev.map((d) => d.id === updated.id ? updated : d) : prev);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }

  async function refreshAndAdvance() {
    const rows = (await api.drafts()) as DraftOut[];
    setDrafts(rows);
    const pool = filter === "all" ? rows : rows.filter((d) =>
      filter === "needs-review" ? d.status === "pending_review" :
      filter === "red" ? d.approval_level === "red" : d.platform === filter);
    const next = pool.find((d) => d.status === "pending_review");
    setSelectedId(next ? next.id : (rows.find((d) => d.status === "pending_review")?.id || null));
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!selected || editing || rejecting) return;
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "a" || e.key === "A") handleApprove();
      else if (e.key === "e" || e.key === "E") { setEditing(true); setEditBody(selected.body); }
      else if (e.key === "r" || e.key === "R") setRejecting(true);
      else if (e.key === "n" || e.key === "N") selectNext();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <Shell full hideTopbar={false}>
      <div className="drafts-shell">
        <div className="drafts-rail" ref={railRef}>
          <div className="rail-head">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <b style={{ fontSize: 13 }}>{t("drafts.reviewQueue")}</b>
              <span className="mono" style={{ fontSize: 12, color: "var(--muted)" }}>{t("drafts.reviewedOf", { reviewed, total })}</span>
            </div>
            <div className="progress-track"><div className="progress-fill" style={{ width: `${pct}%` }} /></div>
          </div>
          <div className="rail-tabs">
            {FILTERS.map(([k, l]) => (
              <button key={k} className={`chip ${filter === k ? "selected" : ""}`} onClick={() => setFilter(k)}>{l}</button>
            ))}
          </div>
          <div className="rail-list">
            {!drafts && <p style={{ padding: 12, color: "var(--muted)" }}>{t("drafts.loading")}</p>}
            {drafts && filtered.length === 0 && (
              <div className="empty"><DraftsIcon /><h3>{t("drafts.nothingHere")}</h3><p>{t("drafts.noMatchFilter")}</p></div>
            )}
            {filtered.map((d) => (
              <div key={d.id} className={`draft-card ${d.id === selectedId ? "active" : ""}`}
                   onClick={() => { setSelectedId(d.id); setEditing(false); setRejecting(false); setConfirmingRed(false); }}>
                <div className="draft-card-top">
                  <PlatformBadge platform={d.platform} />
                  <span className={`safety-dot ${d.approval_level}`} />
                  <span className="draft-status-chip">{d.status === "pending_review" ? t("drafts.needsReview") : d.status}</span>
                </div>
                <div className="draft-card-hook">{d.hook || d.body.slice(0, 80)}</div>
                <div className="draft-card-foot">
                  <span className="mono" style={{ fontSize: 11, color: "var(--muted-2)" }}>
                    {d.relevance ? Math.round(d.relevance) : "—"} {t("drafts.pts")}
                  </span>
                  <PillarTag pillar={d.pillar} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="draft-detail">
          {!selected && (
            <div className="empty" style={{ margin: "70px auto" }}>
              <DraftsIcon /><h3>{t("drafts.allCaughtUp")}</h3><p>{t("drafts.noDraftsToReview")}</p>
            </div>
          )}
          {selected && (
            <>
              <div className="detail-scroll">
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 14 }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                      <PlatformBadge platform={selected.platform} />
                      <PillarTag pillar={selected.pillar} />
                      <ConfidencePill confidence={selected.fact_confidence} />
                    </div>
                    <h2 style={{ fontSize: 19, lineHeight: 1.35 }}
                        className={selected.language === "ar" ? "rtl" : ""}>
                      {selected.hook}
                    </h2>
                  </div>
                  <ScoreBadge score={selected.relevance} />
                </div>

                {selected.status !== "pending_review" && (
                  <div className="reason-banner green" style={{ marginTop: 12 }}>
                    <div><b>{selected.status === "approved" ? t("drafts.approved") : selected.status}</b></div>
                  </div>
                )}

                <div style={{ marginTop: 14 }}>{reasonBanner(selected)}</div>

                {editing ? (
                  <>
                    <div className="section-title">{t("drafts.editDraft")}</div>
                    <textarea className="textarea" style={{ minHeight: 180 }} value={editBody}
                              onChange={(e) => setEditBody(e.target.value)} />
                  </>
                ) : (
                  <div className="platform-preview">
                    <div className="pp-head">
                      <div className="pp-avatar">YA</div>
                      <div><div className="pp-name">Yahya Al Salamah</div><div className="pp-handle">@alsalamah_y</div></div>
                    </div>
                    <div className={`pp-body ${selected.language === "ar" ? "rtl" : ""}`}>{selected.body}</div>
                    <div className="pp-count">{selected.body.length} {t("drafts.characters")}</div>
                  </div>
                )}

                {selected.media_brief && (
                  <>
                    <div className="section-title">{t("drafts.mediaBrief")}</div>
                    <p style={{ fontSize: 13, color: "var(--muted)" }}>{selected.media_brief}</p>
                  </>
                )}

                <details className="disclosure">
                  <summary>{t("drafts.scoreBreakdown")}</summary>
                  <div className="disclosure-body"><BreakdownRows scores={selected.scores} /></div>
                </details>

                <details className="disclosure">
                  <summary>{t("drafts.sourcesAndRefs", { count: selected.sources.length })}</summary>
                  <div className="disclosure-body"><SourcesList sources={selected.sources} /></div>
                </details>

                {rejecting && (
                  <div className="card card-pad" style={{ marginTop: 16, background: "var(--danger-soft)" }}>
                    <div className="section-title" style={{ marginTop: 0 }}>{t("drafts.whyReject")}</div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                      {REASON_TAGS.map((tag) => (
                        <button key={tag} type="button"
                                className={`chip ${selectedReasons.includes(tag) ? "selected" : ""}`}
                                onClick={() => setSelectedReasons((prev) =>
                                  prev.includes(tag) ? prev.filter((r) => r !== tag) : [...prev, tag])}>
                          {tag}
                        </button>
                      ))}
                    </div>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="btn btn-danger btn-sm" disabled={busy || !selectedReasons.length}
                              onClick={handleReject}>{t("drafts.confirmReject")}</button>
                      <button className="btn btn-ghost btn-sm" onClick={() => setRejecting(false)}>{t("drafts.cancel")}</button>
                    </div>
                  </div>
                )}

                {confirmingRed && (
                  <div className="card card-pad" style={{ marginTop: 16, background: "var(--danger-soft)" }}>
                    <p style={{ fontSize: 13, marginBottom: 10 }}>
                      {t("drafts.redConfirmText")}
                    </p>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="btn btn-danger btn-sm" disabled={busy} onClick={() => handleApprove(true)}>
                        {t("drafts.yesApproveAnyway")}
                      </button>
                      <button className="btn btn-ghost btn-sm" onClick={() => setConfirmingRed(false)}>{t("drafts.cancel")}</button>
                    </div>
                  </div>
                )}
              </div>

              <div className="action-bar">
                {selected.status === "pending_review" ? (
                  selected.approval_level === "red" && !confirmingRed ? (
                    <button className="btn btn-danger" onClick={() => setConfirmingRed(true)}>{t("drafts.requiresSignoff")}</button>
                  ) : (
                    <button className="btn btn-primary" disabled={busy} onClick={() => handleApprove()}>
                      <span className="kbd" style={{ background: "rgba(255,255,255,.2)", borderColor: "transparent", color: "inherit" }}>A</span> {t("drafts.approve")}
                    </button>
                  )
                ) : selected.status === "approved" ? (
                  <button className="btn btn-primary" disabled={busy} onClick={handlePublish}>{t("drafts.publishNow")}</button>
                ) : selected.status === "scheduled" ? (
                  <button className="btn" disabled>{t("drafts.scheduledManual")}</button>
                ) : selected.status === "posted" ? (
                  <button className="btn" disabled>{t("drafts.published")}{selected.external_id ? ` · ${selected.external_id}` : ""}</button>
                ) : selected.status === "failed" ? (
                  <button className="btn btn-danger" disabled={busy} onClick={handlePublish}>{t("drafts.publishFailedRetry")}</button>
                ) : (
                  <button className="btn" disabled>{t("drafts.reviewed")}</button>
                )}
                <button className="btn btn-ghost" onClick={() => { setEditing((v) => !v); setEditBody(selected.body); }}>
                  <span className="kbd">E</span> {editing ? t("drafts.cancelEdit") : t("common.edit")}
                </button>
                {editing && <button className="btn btn-primary" disabled={busy} onClick={handleSaveApprove}>{t("drafts.saveApprove")}</button>}
                <button className="btn btn-ghost" onClick={() => setRejecting(true)}><span className="kbd">R</span> {t("drafts.reject")}</button>
                <button className="btn btn-ghost" disabled={busy} onClick={handleRegenerate}><RefreshIcon /> {t("drafts.regenerate")}</button>
                <div className="kbd-legend">
                  <span><span className="kbd">A</span>{t("drafts.kbdApprove")}</span>
                  <span><span className="kbd">E</span>{t("drafts.kbdEdit")}</span>
                  <span><span className="kbd">R</span>{t("drafts.kbdReject")}</span>
                  <span><span className="kbd">N</span>{t("drafts.kbdNext")}</span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      {error && <p style={{ color: "var(--danger)", padding: 12 }}>{t("drafts.errorPrefix")}: {error}</p>}
    </Shell>
  );
}
