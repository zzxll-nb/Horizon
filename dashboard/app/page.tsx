import { DashboardShell } from "@/components/dashboard-shell";
import { getDashboardData, getMarketSnapshot } from "@/lib/dashboard-data";

const staticBuildTimestamp = Date.now();

export default async function Home() {
  const [{ snapshot, source }, marketSnapshot] = await Promise.all([getDashboardData(), getMarketSnapshot()]);
  return <DashboardShell snapshot={snapshot} dataSource={source} marketSnapshot={marketSnapshot} snapshotCheckedAt={staticBuildTimestamp} />;
}
