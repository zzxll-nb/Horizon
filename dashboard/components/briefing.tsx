import { Layers3 } from "lucide-react";

import type { BriefingEvent, DashboardSnapshot } from "@/types/dashboard";

const categoryLabels = { china: "中国", us: "美国", international: "国际", finance: "财经", tech_ai: "科技 / AI" } as const;

export function Briefing({ briefing, isSample }: { briefing: DashboardSnapshot["briefing"]; isSample: boolean }) {
  return (
    <section className="mt-8 rounded-2xl bg-[#F7F7F8] px-5 py-6 sm:px-7 sm:py-7" aria-labelledby="briefing-title">
      <div className="max-w-3xl border-l-2 border-[#FF7A00] pl-4">
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold tracking-[0.13em] text-[#E86F00]">
          <span className="h-px w-6 bg-[#FF7A00]" />每日精选
        </div>
        <h2 id="briefing-title" className="text-xl font-semibold tracking-tight text-zinc-950 sm:text-2xl">{briefing.title}</h2>
        <p className="mt-2 text-[15px] leading-7 text-zinc-600">{briefing.summary}</p>
        {isSample && <p className="mt-3 text-xs leading-5 text-amber-700">当前显示示例数据，仅用于界面预览。</p>}
      </div>

      {briefing.events.length > 0 ? (
        <div className="mt-6 divide-y divide-zinc-200/80 border-t border-zinc-200/80">
          {briefing.events.map((event, index) => <BriefingRow key={event.id} event={event} index={index + 1} />)}
        </div>
      ) : (
        <div className="mt-6 border-t border-zinc-200/80 py-9 text-center text-sm text-zinc-500">暂无可展示的重点情报</div>
      )}
    </section>
  );
}

function BriefingRow({ event, index }: { event: BriefingEvent; index: number }) {
  return (
    <article className="grid gap-3 py-5 md:grid-cols-[38px_minmax(0,1fr)_auto] md:gap-4">
      <div className="flex size-8 items-center justify-center rounded-full bg-white text-sm font-semibold text-[#E86F00]">{String(index).padStart(2, "0")}</div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="break-words text-base font-semibold leading-6 text-zinc-900">{event.title_cn}</h3>
          <Importance level={event.importance.level} score={event.importance.score} />
        </div>
        <p className="mt-1.5 break-words text-sm leading-6 text-zinc-600">{event.summary}</p>
        {event.why_important && <p className="mt-2 border-l border-zinc-300 pl-3 text-[13px] leading-6 text-zinc-500"><span className="font-medium">为什么重要：</span>{event.why_important}</p>}
      </div>
      <div className="flex items-center gap-3 pl-12 text-xs text-zinc-400 md:flex-col md:items-end md:gap-2 md:pl-0">
        <span className="rounded-full bg-white px-2.5 py-1 text-zinc-600">{categoryLabels[event.category]}</span>
        <span className="flex items-center gap-1"><Layers3 size={13} />{event.source_count} 个来源</span>
      </div>
    </article>
  );
}

export function Importance({ level, score }: { level: "high" | "medium" | "low"; score: number }) {
  const label = level === "high" ? "高重要性" : level === "medium" ? "中等" : "一般";
  const color = level === "high" ? "bg-orange-50 text-[#E86F00]" : level === "medium" ? "bg-zinc-200/70 text-zinc-600" : "bg-zinc-100 text-zinc-400";
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${color}`}>{label} · {score}</span>;
}
