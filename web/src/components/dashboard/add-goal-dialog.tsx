"use client";

import { useState } from "react";

import { useCreateGoal, useUpdateGoal } from "@/hooks/use-goals";
import { apiErrorMessage } from "@/lib/api-client";
import type { Goal } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface AddGoalDialogProps {
  goal?: Goal;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function AddGoalDialog({ goal, open: controlledOpen, onOpenChange }: AddGoalDialogProps) {
  const isEditing = Boolean(goal);
  const createGoal = useCreateGoal();
  const updateGoal = useUpdateGoal();
  const [uncontrolledOpen, setUncontrolledOpen] = useState(false);
  const open = controlledOpen ?? uncontrolledOpen;
  const setOpen = onOpenChange ?? setUncontrolledOpen;

  const [name, setName] = useState(goal?.name ?? "");
  const [target, setTarget] = useState(goal ? String(goal.target_amount_minor / 100) : "");
  const [current, setCurrent] = useState(goal ? String(goal.current_amount_minor / 100) : "0");
  const [targetDate, setTargetDate] = useState(goal?.target_date ?? "");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const input = {
        name,
        target_amount_minor: Math.round((Number.parseFloat(target) || 0) * 100),
        current_amount_minor: Math.round((Number.parseFloat(current) || 0) * 100),
        target_date: targetDate || null,
      };
      if (isEditing && goal) {
        await updateGoal.mutateAsync({ id: goal.id, ...input });
      } else {
        await createGoal.mutateAsync(input);
        setName("");
        setTarget("");
        setCurrent("0");
        setTargetDate("");
      }
      setOpen(false);
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't save that goal."));
    }
  }

  const isPending = createGoal.isPending || updateGoal.isPending;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {!isEditing && <DialogTrigger render={<Button size="sm" />}>Add goal</DialogTrigger>}
      {open && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{isEditing ? "Edit goal" : "Add goal"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="goal-name">Name</Label>
              <Input id="goal-name" required value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="goal-target">Target amount</Label>
                <Input
                  id="goal-target"
                  type="number"
                  min="0.01"
                  step="0.01"
                  required
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="goal-current">Current amount</Label>
                <Input
                  id="goal-current"
                  type="number"
                  min="0"
                  step="0.01"
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="goal-date">Target date (optional)</Label>
              <Input id="goal-date" type="date" value={targetDate ?? ""} onChange={(e) => setTargetDate(e.target.value)} />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button type="submit" disabled={isPending}>
                {isPending ? "Saving…" : isEditing ? "Save changes" : "Add goal"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      )}
    </Dialog>
  );
}
