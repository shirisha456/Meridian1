"use client";

import { useMemo, useState } from "react";
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

import { useBudgetActual, useUpsertBudget } from "@/hooks/use-budgets";
import { formatMinorUnits } from "@/lib/money";
import { apiErrorMessage } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";

function monthIso(offsetFromCurrent: number): string {
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth() + offsetFromCurrent, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

function monthLabel(iso: string): string {
  const [year, month] = iso.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

export default function BudgetsPage() {
  const [monthOffset, setMonthOffset] = useState(0);
  const month = monthIso(monthOffset);
  const { data: actuals, isLoading } = useBudgetActual(month);
  const upsertBudget = useUpsertBudget();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSave(categoryId: string) {
    const raw = drafts[categoryId];
    const dollars = Number.parseFloat(raw ?? "");
    if (!Number.isFinite(dollars) || dollars <= 0) {
      setError("Enter an amount greater than $0.");
      return;
    }
    setError(null);
    setSavingId(categoryId);
    try {
      await upsertBudget.mutateAsync({
        category_id: categoryId,
        month,
        amount_minor: Math.round(dollars * 100),
      });
      setDrafts((prev) => ({ ...prev, [categoryId]: "" }));
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't save that budget."));
    } finally {
      setSavingId(null);
    }
  }

  const rows = useMemo(() => actuals ?? [], [actuals]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Budgets</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon-sm" onClick={() => setMonthOffset((o) => o - 1)}>
            <ChevronLeftIcon />
            <span className="sr-only">Previous month</span>
          </Button>
          <span className="min-w-36 text-center text-sm font-medium">{monthLabel(month)}</span>
          <Button variant="outline" size="icon-sm" onClick={() => setMonthOffset((o) => o + 1)}>
            <ChevronRightIcon />
            <span className="sr-only">Next month</span>
          </Button>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No categories to budget yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((row) => {
            const overBudget = row.budgeted_minor > 0 && row.actual_minor > row.budgeted_minor;
            const pct = row.budgeted_minor > 0 ? Math.min(100, (row.actual_minor / row.budgeted_minor) * 100) : 0;
            return (
              <Card key={row.category_id}>
                <CardHeader>
                  <CardTitle>{row.category_name}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <div className="flex items-baseline justify-between text-sm">
                    <span className={overBudget ? "font-medium text-destructive" : "font-medium"}>
                      {formatMinorUnits(row.actual_minor)}
                    </span>
                    <span className="text-muted-foreground">of {formatMinorUnits(row.budgeted_minor)}</span>
                  </div>
                  {row.budgeted_minor > 0 && (
                    <Progress value={pct} indicatorClassName={overBudget ? "bg-destructive" : undefined} />
                  )}
                  <div className="flex gap-2">
                    <Input
                      type="number"
                      min="0.01"
                      step="0.01"
                      placeholder={formatMinorUnits(row.budgeted_minor)}
                      value={drafts[row.category_id] ?? ""}
                      onChange={(e) => setDrafts((prev) => ({ ...prev, [row.category_id]: e.target.value }))}
                    />
                    <Button
                      size="sm"
                      disabled={savingId === row.category_id || !drafts[row.category_id]}
                      onClick={() => void handleSave(row.category_id)}
                    >
                      Save
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
