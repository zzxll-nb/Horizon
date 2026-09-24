import { ArrowUpRight, ChevronDown, Layers3 } from "lucide-react";

import { Importance } from "@/components/briefing";
import type { DashboardSnapshot, NewsEvent } from "@/types/dashboard";

const categoryLabels = { china: "中国", us: "美国", international: "国际", finance: "财经", tech_ai: "科技 / AI" } as const;

export function NewsList({ news }: { news: DashboardSnapshot["news"] }) {
  if (news.length === 0) {
    return <div className="rounded-2xl bg-zinc-50 px-6 py-14 text-center text-sm text-zinc-500">暂无相关情报</div>;
  }

  return (
    <div className="divide-y divide-zinc-200 border-t border-zinc-200">
      {news.map((item) => <NewsRow key={item.id} item={item} />)}
    </div>
  );
}

function NewsRow({ item }: { item: NewsEvent }) {
  const sourceLabel = item.sources.length > 1 ? `${item.primary_source} 等 ${item.sources.length} 个来源` : item.primary_source;
  return (
    <article className="grid gap-4 py-6 sm:grid-cols-[92px_minmax(0,1fr)] lg:grid-cols-[108px_minmax(0,1fr)_132px]">
      <div className="flex items-start gap-2 sm:block">
        <span className="inline-flex rounded-full bg-orange-50 px-2.5 py-1 text-xs font-medium text-[#E86F00]">{categoryLabels[item.category]}</span>
        <div className="mt-0 text-xs text-zinc-400 sm:mt-2">{formatPublished(item.published_at)}</div>
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="break-words text-[17px] font-semibold leading-7 tracking-tight text-zinc-950">{item.title_cn}</h3>
          <Importance level={item.importance.level} score={item.importance.score} />
        </div>
        <p className="mt-2 break-words text-[15px] leading-7 text-zinc-600">{item.summary}</p>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-zinc-400">
          <span className="flex items-center gap-1.5"><Layers3 size={13} />{sourceLabel}</span>
        </div>
        {item.why_important && <p className="mt-2.5 max-w-3xl border-l border-zinc-200 pl-3 text-xs leading-5 text-zinc-500"><span className="font-medium text-zinc-600">为什么重要：</span>{item.why_important}</p>}
        {item.analysis && (
          <details className="group mt-4 max-w-4xl rounded-xl bg-zinc-50 px-4 py-3 open:pb-5">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm font-medium text-zinc-700 marker:content-none">
              查看深度分析
              <ChevronDown size={15} className="text-zinc-400 group-open:rotate-180" />
            </summary>
            <div className="mt-4 whitespace-pre-line text-[15px] leading-8 text-zinc-700">{item.analysis}</div>
            {!!item.watch_factors?.length && (
              <div className="mt-5 border-t border-zinc-200 pt-4">
                <h4 className="text-sm font-semibold text-zinc-800">后续观察指标</h4>
                <ul className="mt-2 space-y-1.5 text-sm leading-6 text-zinc-600">
                  {item.watch_factors.map((factor) => <li key={factor}>• {factor}</li>)}
                </ul>
              </div>
            )}
            {!!item.related_assets?.length && (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-zinc-500">关联资产</span>
                {item.related_assets.map((asset) => <span key={asset} className="rounded-full bg-white px-2.5 py-1 text-xs text-zinc-600">{asset}</span>)}
              </div>
            )}
          </details>
        )}
      </div>
      <div className="flex items-end justify-start sm:col-start-2 lg:col-start-auto lg:justify-end">
        <a className="inline-flex items-center gap-1.5 text-sm font-medium text-zinc-700 transition-colors hover:text-[#E86F00]" href={item.primary_url} target="_blank" rel="noreferrer">
          查看原文<ArrowUpRight size={15} />
        </a>
      </div>
    </article>
  );
}

function formatPublished(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
