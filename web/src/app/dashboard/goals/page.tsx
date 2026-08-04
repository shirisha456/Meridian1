"use client";

import { useState } from "react";

import { useDeleteGoal, useGoals } from "@/hooks/use-goals";
import { formatMinorUnits } from "@/lib/money";
import type { Goal } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { AddGoalDialog } from "@/components/dashboard/add-goal-dialog";

export default function GoalsPage() {
  const { data, isLoading } = useGoals();
  const deleteGoal = useDeleteGoal();
  const [editingGoal, setEditingGoal] = useState<Goal | null>(null);

  const goals = data?.items ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Goals</h1>
        <AddGoalDialog />
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : goals.length === 0 ? (
        <p className="text-sm text-muted-foreground">No savings goals yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {goals.map((goal) => {
            const pct =
              goal.target_amount_minor > 0
                ? Math.min(100, (goal.current_amount_minor / goal.target_amount_minor) * 100)
                : 0;
            return (
              <Card key={goal.id}>
                <CardHeader>
                  <CardTitle>{goal.name}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="font-medium">{formatMinorUnits(goal.current_amount_minor)}</span>
                    <span className="text-muted-foreground">of {formatMinorUnits(goal.target_amount_minor)}</span>
                  </div>
                  <Progress value={pct} />
                  {goal.target_date && (
                    <p className="text-xs text-muted-foreground">Target date: {goal.target_date}</p>
                  )}
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => setEditingGoal(goal)}>
                      Edit
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => void deleteGoal.mutateAsync(goal.id)}
                      disabled={deleteGoal.isPending}
                    >
                      Remove
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {editingGoal && (
        <AddGoalDialog goal={editingGoal} open onOpenChange={(open) => !open && setEditingGoal(null)} />
      )}
    </div>
  );
}
