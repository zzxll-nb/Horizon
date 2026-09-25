import {
  Bot,
  BriefcaseBusiness,
  Cpu,
  Globe2,
  House,
  Landmark,
  Settings,
  ShieldCheck,
  X,
  type LucideIcon,
} from "lucide-react";

import type { CategoryId, DashboardSnapshot } from "@/types/dashboard";

const icons: Record<CategoryId, LucideIcon> = {
  markets: Globe2,
  finance: BriefcaseBusiness,
  investing: ShieldCheck,
  macro: Landmark,
  tech_ai: Cpu,
};

interface SidebarProps {
  categories: DashboardSnapshot["categories"];
  activeCategory: CategoryId | "all";
  mobileOpen: boolean;
  onClose: () => void;
  onSelect: (category: CategoryId | "all") => void;
}

export function Sidebar({ categories, activeCategory, mobileOpen, onClose, onSelect }: SidebarProps) {
  const select = (category: CategoryId | "all") => {
    onSelect(category);
    onClose();
  };

  return (
    <>
      {mobileOpen && (
        <button className="fixed inset-0 z-40 bg-black/20 lg:hidden" aria-label="关闭导航" onClick={onClose} />
      )}
      <aside className={`fixed inset-y-0 left-0 z-50 flex w-[224px] flex-col border-r border-zinc-200 bg-white px-4 py-5 transition-transform lg:translate-x-0 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="mb-8 flex items-center justify-between px-2">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-orange-50 text-orange-600">
              <Bot size={19} strokeWidth={2.2} />
            </span>
            <div className="text-[15px] font-semibold tracking-tight text-zinc-950">赵哲咺工作台</div>
          </div>
          <button className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100 lg:hidden" aria-label="关闭导航" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <nav className="space-y-1" aria-label="主要导航">
          <NavButton active={activeCategory === "all"} icon={House} label="今日情报" onClick={() => select("all")} />
          <div className="px-3 pb-2 pt-6 text-xs font-medium tracking-[0.12em] text-zinc-400">分类</div>
          {categories.map((category) => (
            <NavButton
              key={category.id}
              active={activeCategory === category.id}
              icon={icons[category.id]}
              label={category.display_name}
              onClick={() => select(category.id)}
            />
          ))}
        </nav>

        <div className="mt-auto border-t border-zinc-100 pt-4">
          <button className="flex w-full cursor-not-allowed items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-zinc-400" disabled>
            <Settings size={17} />设置
            <span className="ml-auto text-[11px]">稍后</span>
          </button>
        </div>
      </aside>
    </>
  );
}

function NavButton({ active, icon: Icon, label, onClick }: { active: boolean; icon: LucideIcon; label: string; onClick: () => void }) {
  return (
    <button
      className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${active ? "bg-orange-50 text-[#E86F00]" : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-950"}`}
      onClick={onClick}
    >
      <Icon size={17} strokeWidth={active ? 2.3 : 1.9} />
      {label}
    </button>
  );
}
