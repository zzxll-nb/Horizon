export type CategoryId = "markets" | "finance" | "investing" | "macro" | "tech_ai";
export type ImportanceLevel = "high" | "medium" | "low";

export interface Importance {
  score: number;
  level: ImportanceLevel;
}

export interface NewsSource {
  name: string;
  url: string;
  published_at: string | null;
}

export interface NewsEvent {
  id: string;
  title_cn: string;
  title_original: string | null;
  summary: string;
  analysis?: string | null;
  why_important: string | null;
  watch_factors?: string[];
  related_assets?: string[];
  content_kind?: "news" | "background_research";
  category: CategoryId;
  importance: Importance;
  published_at: string;
  updated_at: string | null;
  sources: NewsSource[];
  primary_source: string;
  primary_url: string;
}

export interface BriefingEvent {
  id: string;
  title_cn: string;
  summary: string;
  why_important: string | null;
  content_kind?: "news" | "background_research";
  category: CategoryId;
  importance: Importance;
  source_count: number;
  source_names: string[];
  published_at: string;
}

export interface DashboardSnapshot {
  schema_version: "1.2";
  data_status: "live" | "sample";
  fixture_note?: string | null;
  generated_at: string;
  period_start: string;
  period_end: string;
  briefing: {
    title: string;
    summary: string;
    events: BriefingEvent[];
  };
  news: NewsEvent[];
  categories: Array<{ id: CategoryId; display_name: string }>;
  market: Record<string, unknown> | null;
}

export type MarketAssetStatus = "live" | "stale" | "unavailable" | "sample";
export type MarketSnapshotStatus = "live" | "partial" | "stale" | "unavailable" | "sample";

export interface MarketAsset {
  id: "sp500" | "nasdaq_composite" | "dow_jones" | "gold" | "wti" | "bitcoin" | "us10y";
  name: string;
  symbol: string;
  current_value: number | null;
  change: number | null;
  change_percent: number | null;
  updated_at: string | null;
  data_status: MarketAssetStatus;
}

export interface MarketSnapshot {
  schema_version: "1.0";
  data_status: MarketSnapshotStatus;
  generated_at: string;
  provider: string;
  assets: MarketAsset[];
}
