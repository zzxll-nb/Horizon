import { readFile } from "node:fs/promises";
import path from "node:path";

import type { DashboardSnapshot, MarketSnapshot } from "@/types/dashboard";

const DATA_ROOT = path.resolve(process.cwd(), "..", "data");

async function readSnapshot(filePath: string): Promise<DashboardSnapshot> {
  const content = await readFile(filePath, "utf8");
  const snapshot = JSON.parse(content) as DashboardSnapshot;

  if (snapshot.schema_version !== "1.2" || !Array.isArray(snapshot.news)) {
    throw new Error(`不支持的 DashboardSnapshot：${filePath}`);
  }
  return snapshot;
}

export async function getDashboardSnapshot(): Promise<DashboardSnapshot> {
  return (await getDashboardData()).snapshot;
}

export type DashboardDataSource = "latest" | "sample";

export interface DashboardData {
  snapshot: DashboardSnapshot;
  source: DashboardDataSource;
}

export async function getDashboardData(): Promise<DashboardData> {
  const latestPath = path.join(DATA_ROOT, "dashboard", "latest.json");
  const examplePath = path.join(DATA_ROOT, "dashboard-snapshot.example.json");

  try {
    return { snapshot: await readSnapshot(latestPath), source: "latest" };
  } catch (error) {
    const missingLatest =
      error instanceof Error && "code" in error && error.code === "ENOENT";
    if (!missingLatest) {
      console.warn("latest.json 读取失败，回退到示例数据。", error);
    }
    return { snapshot: await readSnapshot(examplePath), source: "sample" };
  }
}

export async function getMarketSnapshot(): Promise<MarketSnapshot | null> {
  const marketPath = path.join(DATA_ROOT, "market", "latest.json");
  try {
    const content = await readFile(marketPath, "utf8");
    const snapshot = JSON.parse(content) as MarketSnapshot;
    if (
      snapshot.schema_version !== "1.0"
      || !Array.isArray(snapshot.assets)
      || !snapshot.assets.every((asset) => typeof asset.id === "string" && typeof asset.name === "string" && typeof asset.symbol === "string" && typeof asset.data_status === "string")
    ) {
      throw new Error(`不支持的 MarketSnapshot：${marketPath}`);
    }
    return snapshot;
  } catch (error) {
    const missingMarket = error instanceof Error && "code" in error && error.code === "ENOENT";
    if (!missingMarket) {
      console.warn("market/latest.json 读取失败，市场数据不可用。", error);
    }
    return null;
  }
}
