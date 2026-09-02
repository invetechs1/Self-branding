// Thin client-side fetch wrapper — always calls same-origin /api/proxy/*,
// never the backend directly (see app/api/proxy/[...path]/route.ts).

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api/proxy${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(`${resp.status} ${resp.statusText}: ${body}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  clusters: () => request("/clusters"),
  cluster: (id: string) => request(`/clusters/${id}`),
  opportunities: () => request("/opportunities"),
  dismissOpportunity: (id: string) => request(`/opportunities/${id}/dismiss`, { method: "POST" }),
  drafts: (params?: { platform?: string; safety?: string }) => {
    const qs = new URLSearchParams();
    if (params?.platform) qs.set("platform", params.platform);
    if (params?.safety) qs.set("safety", params.safety);
    const suffix = qs.toString() ? `?${qs}` : "";
    return request(`/drafts${suffix}`);
  },
  draft: (id: string) => request(`/drafts/${id}`),
  rejectedDrafts: () => request("/drafts/rejected"),
  generateDraft: (clusterId: string, platform: string, language?: string) =>
    request("/drafts/generate", {
      method: "POST",
      body: JSON.stringify({ cluster_id: clusterId, platform, language }),
    }),
  approveDraft: (id: string, confirmedRed = false) =>
    request(`/drafts/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ confirmed_red: confirmedRed }),
    }),
  editApproveDraft: (id: string, body: string, confirmedRed = false) =>
    request(`/drafts/${id}/edit-approve`, {
      method: "POST",
      body: JSON.stringify({ body, confirmed_red: confirmedRed }),
    }),
  rejectDraft: (id: string, reasonTags: string[], comment?: string) =>
    request(`/drafts/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason_tags: reasonTags, comment }),
    }),
  regenerateDraft: (id: string, mode = "full") =>
    request(`/drafts/${id}/regenerate`, {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
  publishDraft: (id: string) => request(`/drafts/${id}/publish`, { method: "POST" }),

  // ── Performance & Learning ──
  performanceSummary: () => request("/performance/summary"),
  performancePosts: () => request("/performance/posts"),
  recomputeLearning: () => request("/performance/recompute", { method: "POST" }),

  // ── Settings ──
  profile: () => request("/settings/profile"),
  knowledge: () => request("/settings/knowledge"),
  addKnowledge: (kind: string, title: string, body: string, isPublic: boolean) =>
    request("/settings/knowledge", {
      method: "POST",
      body: JSON.stringify({ kind, title, body, is_public: isPublic }),
    }),
  updateKnowledge: (id: string, patch: { title?: string; body?: string; is_public?: boolean }) =>
    request(`/settings/knowledge/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  pillarSettings: () => request("/settings/pillars"),
  updatePillarShare: (key: string, targetShare: number) =>
    request(`/settings/pillars/${key}`, {
      method: "PATCH",
      body: JSON.stringify({ target_share: targetShare }),
    }),
  topics: () => request("/settings/topics"),
  addTopic: (name: string, tier = 3) =>
    request("/settings/topics", { method: "POST", body: JSON.stringify({ name, tier }) }),
  removeTopic: (id: number) => request(`/settings/topics/${id}`, { method: "DELETE" }),
  addExcludedTopic: (topic: string) =>
    request("/settings/topics/excluded", { method: "POST", body: JSON.stringify({ topic }) }),
  removeExcludedTopic: (topic: string) =>
    request(`/settings/topics/excluded/${encodeURIComponent(topic)}`, { method: "DELETE" }),
  sourceSettings: () => request("/settings/sources"),
  toggleSource: (id: number) => request(`/settings/sources/${id}/toggle`, { method: "POST" }),
  publishingRules: () => request("/settings/publishing"),
  approvalThresholds: () => request("/settings/approval-thresholds"),
  safetyConfig: () => request("/settings/safety"),
  systemConfig: () => request("/settings/system"),

  // ── Discovery ("Fetch latest") ──
  discoveryStatus: () => request("/discover/status"),
  triggerDiscovery: () => request("/discover/run", { method: "POST" }),
};
