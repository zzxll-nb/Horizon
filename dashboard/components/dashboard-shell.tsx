"use client";

import { useMemo, useState } from "react";

import { Briefing } from "@/components/briefing";
import { CategoryFilter } from "@/components/category-filter";
import { Header } from "@/components/header";
import { MarketOverview } from "@/components/market-overview";
import { NewsList } from "@/components/news-list";
import { Sidebar } from "@/components/sidebar";
import type { DashboardDataSource } from "@/lib/dashboard-data";
import type { CategoryId, DashboardSnapshot, MarketSnapshot } from "@/types/dashboard";

export function DashboardShell({ snapshot, dataSource, marketSnapshot, snapshotCheckedAt }: { snapshot: DashboardSnapshot; dataSource: DashboardDataSource; marketSnapshot: MarketSnapshot | null; snapshotCheckedAt: number }) {
  const [category, setCategory] = useState<CategoryId | "all">("all");
  const [mobileOpen, setMobileOpen] = useState(false);
  const news = useMemo(
    () => [...snapshot.news]
      .filter((item) => category === "all" || item.category === category)
      .sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at)),
    [category, snapshot.news],
  );

  const selectCategory = (next: CategoryId | "all") => {
    setCategory(next);
    if (next !== "all") {
      window.setTimeout(() => document.querySelector("#latest-news")?.scrollIntoView({ behavior: "smooth" }), 0);
    }
  };
  const isSample = dataSource === "sample" || snapshot.data_status === "sample";
  const isNewsStale = snapshotCheckedAt - Date.parse(snapshot.generated_at) > 2 * 60 * 60 * 1000;

  return (
    <div className="min-h-screen bg-white">
      <Sidebar categories={snapshot.categories} activeCategory={category} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} onSelect={selectCategory} />
      <main className="lg:pl-[224px]">
        <div className="mx-auto w-full max-w-[1440px] px-5 py-6 sm:px-8 sm:py-8 lg:px-10 xl:px-12">
          <Header periodEnd={snapshot.period_end} generatedAt={snapshot.generated_at} isSample={isSample} isStale={isNewsStale} onMenu={() => setMobileOpen(true)} />
          <Briefing briefing={snapshot.briefing} isSample={isSample} />

          <section id="latest-news" className="mt-12 scroll-mt-6" aria-labelledby="latest-title">
            <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <h2 id="latest-title" className="text-xl font-semibold tracking-tight text-zinc-950">最新情报</h2>
                <p className="mt-1 text-sm text-zinc-500">按发布时间排序 · 当前显示 {news.length} 条</p>
              </div>
              <CategoryFilter categories={snapshot.categories} active={category} onChange={selectCategory} />
            </div>
            <NewsList news={news} />
          </section>

          <MarketOverview snapshot={marketSnapshot} snapshotCheckedAt={snapshotCheckedAt} />

          <footer className="mt-12 border-t border-zinc-200 py-6 text-xs text-zinc-400">
            AI 全球情报工作台 · 数据周期 {formatPeriod(snapshot.period_start)}—{formatPeriod(snapshot.period_end)}
          </footer>
        </div>
      </main>
    </div>
  );
}

function formatPeriod(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", month: "numeric", day: "numeric", hour: "2-digit" }).format(new Date(value));
}
