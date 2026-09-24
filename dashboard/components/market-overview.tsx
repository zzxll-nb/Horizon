import type { MarketAsset, MarketSnapshot } from "@/types/dashboard";

export function MarketOverview({ snapshot, snapshotCheckedAt }: { snapshot: MarketSnapshot | null; snapshotCheckedAt: number }) {
  if (!snapshot || snapshot.assets.length === 0) {
    return (
      <section className="mt-12" aria-labelledby="market-title">
        <h2 id="market-title" className="text-lg font-semibold tracking-tight text-zinc-950">市场概览</h2>
        <div className="mt-4 rounded-xl bg-zinc-50 px-5 py-7 text-sm text-zinc-500">市场数据暂不可用</div>
      </section>
    );
  }

  const isStale = snapshotCheckedAt - Date.parse(snapshot.generated_at) > 90 * 60 * 1000;
  const status = isStale && snapshot.data_status === "live" ? "stale" : snapshot.data_status;

  return (
    <section className="mt-12" aria-labelledby="market-title">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 id="market-title" className="text-lg font-semibold tracking-tight text-zinc-950">市场概览</h2>
          <p className="mt-1 text-xs text-zinc-400">{isStale ? "数据可能已过期" : marketStatusLabel(status)} · 更新于 {formatTime(snapshot.generated_at)}</p>
        </div>
        <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${statusStyle(status)}`}>{isStale ? "数据可能已过期" : marketStatusLabel(status)}</span>
      </div>
      <div className="hide-scrollbar mt-4 flex snap-x gap-3 overflow-x-auto pb-2 xl:grid xl:grid-cols-7 xl:overflow-visible">
        {snapshot.assets.map((asset) => <MarketCard key={asset.id} asset={asset} />)}
      </div>
    </section>
  );
}

function MarketCard({ asset }: { asset: MarketAsset }) {
  const unavailable = asset.data_status === "unavailable" || asset.current_value === null;
  const changeClass = asset.change_percent === null || asset.change_percent === 0
    ? "text-zinc-500"
    : asset.change_percent > 0 ? "text-emerald-600" : "text-zinc-500";

  return (
    <div className="min-w-[148px] snap-start rounded-xl bg-zinc-50 px-4 py-3">
      <div className="truncate text-xs font-medium text-zinc-500" title={asset.name}>{asset.name}</div>
      {unavailable ? (
        <div className="mt-2 text-sm font-medium text-zinc-400">暂时无法获取</div>
      ) : (
        <>
          <div className="mt-2 text-[15px] font-semibold tracking-tight text-zinc-950">{formatValue(asset)}</div>
          <div className={`mt-1 text-xs ${changeClass}`}>{formatChange(asset)}</div>
        </>
      )}
      {asset.data_status === "stale" && <div className="mt-1.5 text-[11px] text-amber-700">缓存数据</div>}
    </div>
  );
}

function formatValue(asset: MarketAsset) {
  const value = asset.current_value ?? 0;
  if (asset.id === "us10y") return `${value.toFixed(2)}%`;
  if (asset.id === "gold" || asset.id === "wti" || asset.id === "bitcoin") {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: asset.id === "bitcoin" ? 0 : 2 }).format(value);
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
}

function formatChange(asset: MarketAsset) {
  if (asset.change === null || asset.change_percent === null) return "—";
  const prefix = asset.change > 0 ? "+" : "";
  const percentPrefix = asset.change_percent > 0 ? "+" : "";
  return `${prefix}${asset.change.toFixed(2)} · ${percentPrefix}${asset.change_percent.toFixed(2)}%`;
}

function marketStatusLabel(status: MarketSnapshot["data_status"]) {
  return ({ live: "最新市场数据", partial: "部分更新", stale: "缓存数据", unavailable: "暂不可用", sample: "示例数据" })[status];
}

function statusStyle(status: MarketSnapshot["data_status"]) {
  return status === "live" ? "bg-zinc-100 text-zinc-600" : status === "sample" ? "bg-amber-50 text-amber-700" : "bg-zinc-100 text-zinc-500";
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
