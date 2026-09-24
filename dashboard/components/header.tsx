import { Menu, Search } from "lucide-react";

export function Header({ periodEnd, generatedAt, isSample, isStale, onMenu }: { periodEnd: string; generatedAt: string; isSample: boolean; isStale: boolean; onMenu: () => void }) {
  return (
    <header className="flex flex-col gap-5 border-b border-zinc-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex items-start gap-3">
        <button className="mt-0.5 rounded-xl border border-zinc-200 p-2.5 text-zinc-600 lg:hidden" aria-label="打开导航" onClick={onMenu}>
          <Menu size={19} />
        </button>
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-950 sm:text-[28px]">今日情报</h1>
            {isSample ? (
              <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">当前为示例数据</span>
            ) : isStale ? (
              <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">数据可能已过期</span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-zinc-500"><span className="size-1.5 rounded-full bg-emerald-500" />最新数据</span>
            )}
          </div>
          <p className="mt-1.5 text-sm text-zinc-500">{formatFullDate(periodEnd)}</p>
        </div>
      </div>

      <div className="flex flex-col gap-3 sm:items-end">
        <p className="text-xs text-zinc-400">最后更新 {formatTime(generatedAt)}</p>
        <label className="flex h-10 w-full items-center gap-2 rounded-xl bg-zinc-100 px-3 text-zinc-400 sm:w-[240px]">
          <Search size={16} />
          <input className="min-w-0 flex-1 bg-transparent text-sm text-zinc-700 outline-none placeholder:text-zinc-400" placeholder="搜索功能即将支持" aria-label="搜索功能即将支持" readOnly />
        </label>
      </div>
    </header>
  );
}

function formatFullDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date(value));
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
