// Mirrors backend/app/api/routers/*.py response models exactly — keep in sync by hand.

export interface SourceRef {
  name: string;
  credibility: number;
}

export interface ArticleOut {
  id: string;
  title: string;
  url: string;
  source: SourceRef | null;
  relevance: number | null;
  pillar: string | null;
  region: string | null;
  scores: Record<string, number> | null;
}

export interface ClusterOut {
  id: string;
  headline: string;
  source_count: number;
  fact_confidence: number | null;
  relevance: number | null;
  pillar: string | null;
  region: string | null;
  freshness: string | null;
}

export interface OpportunityOut {
  id: string;
  cluster_id: string;
  opportunity_type: string;
  label: string;
  status: string;
  headline: string;
  pillar: string | null;
  region: string | null;
  relevance: number | null;
  fact_confidence: number | null;
  source_count: number;
}

export interface ClusterDetailOut extends ClusterOut {
  articles: ArticleOut[];
  opportunities: OpportunityOut[];
}

export type SafetyLevel = "green" | "yellow" | "red";

export interface DraftOut {
  id: string;
  platform: string;
  language: string;
  pillar: string | null;
  hook: string | null;
  body: string;
  media_brief: string | null;
  approval_level: SafetyLevel;
  review_notes: string | null;
  fact_confidence: number | null;
  relevance: number | null;
  status: string;
  external_id: string | null;
  scores: Record<string, number> | null;
  sources: SourceRef[];
}

export interface RejectedDraftOut extends DraftOut {
  rejected_at: string | null;
  reason_tags: string[];
  comment: string | null;
  rejected_by: string | null;
}

// ── Discovery ──

export interface DiscoveryStatus {
  status: "idle" | "running" | "error";
  started_at: string | null;
  completed_at: string | null;
  last_result: { fetched: number; new: number; kept: number; clusters: number } | null;
  error: string | null;
}

// ── Performance & Learning ──

export interface PlatformPerformance {
  platform: string;
  avg_engagement_rate: number;
  post_count: number;
}

export interface PillarMix {
  key: string;
  label: string;
  target_share: number;
  actual_share: number;
  multiplier: number;
}

export interface LearnedInsight {
  pillar: string;
  label: string;
  text: string;
}

export interface PerformanceSummary {
  posts_published: number;
  approved: number;
  rejected: number;
  approval_rate: number | null;
  total_impressions: number;
  avg_engagement_rate: number;
  platform_performance: PlatformPerformance[];
  pillar_mix: PillarMix[];
  learned: LearnedInsight[];
  sample_size: number;
}

export interface PublishedPost {
  id: string;
  platform: string;
  pillar: string | null;
  hook: string | null;
  posted_at: string | null;
  impressions: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  engagement_rate: number | null;
}

// ── Settings ──

export interface ProfileOut {
  name_ar: string;
  name_en: string;
  headline: string | null;
  city: string | null;
  accounts: Record<string, { connected: boolean; note?: string | null }>;
}

export interface KnowledgeItem {
  id: string;
  kind: string;
  title: string;
  body: string;
  is_public: boolean;
  source: string | null;
}

export interface PillarSetting {
  key: string;
  label_ar: string;
  label_en: string;
  target_share: number;
  multiplier: number;
}

export interface InterestOut {
  id: number;
  name: string;
  tier: number;
  aliases: string[];
  pillar: string | null;
}

export interface TopicsOut {
  tracked: InterestOut[];
  excluded: string[];
}

export interface SourceSetting {
  id: number;
  name: string;
  url: string;
  source_type: string;
  credibility: number;
  region: string | null;
  enabled: boolean;
  last_fetched_at: string | null;
  failure_count: number;
}

export interface PublishingRules {
  auto_publish_green: boolean;
  require_approval: boolean;
  manual_period_locked: boolean;
  manual_period_ends: string;
}
