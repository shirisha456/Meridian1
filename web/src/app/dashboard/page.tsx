import { AccountsSection } from "@/components/dashboard/accounts-section";
import { InsightCard } from "@/components/dashboard/insight-card";
import { TransactionsSection } from "@/components/dashboard/transactions-section";

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-10">
      <InsightCard />
      <AccountsSection />
      <TransactionsSection />
    </div>
  );
}
