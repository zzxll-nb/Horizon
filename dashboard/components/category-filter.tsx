import type { CategoryId, DashboardSnapshot } from "@/types/dashboard";

export function CategoryFilter({ categories, active, onChange }: { categories: DashboardSnapshot["categories"]; active: CategoryId | "all"; onChange: (category: CategoryId | "all") => void }) {
  const options = [{ id: "all" as const, display_name: "全部" }, ...categories];
  return (
    <div className="hide-scrollbar flex gap-2 overflow-x-auto" aria-label="新闻分类筛选">
      {options.map((category) => (
        <button
          key={category.id}
          className={`shrink-0 rounded-full px-3.5 py-2 text-sm font-medium transition-colors ${active === category.id ? "bg-orange-50 text-[#E86F00]" : "bg-zinc-100 text-zinc-600 hover:bg-orange-50 hover:text-[#E86F00]"}`}
          onClick={() => onChange(category.id)}
        >
          {category.display_name}
        </button>
      ))}
    </div>
  );
}
