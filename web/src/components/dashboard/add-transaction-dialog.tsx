"use client";

import { useState } from "react";

import { useAccounts } from "@/hooks/use-accounts";
import { useCategories } from "@/hooks/use-categories";
import { useCreateTransaction } from "@/hooks/use-transactions";
import { apiErrorMessage } from "@/lib/api-client";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function AddTransactionDialog() {
  const { data: accounts } = useAccounts();
  const { data: categories } = useCategories();
  const createTransaction = useCreateTransaction();

  const [open, setOpen] = useState(false);
  const [accountId, setAccountId] = useState("");
  const [categoryId, setCategoryId] = useState<string>("");
  const [merchant, setMerchant] = useState("");
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());
  const [error, setError] = useState<string | null>(null);

  const accountOptions = accounts?.items ?? [];

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const magnitude = Math.abs(Number.parseFloat(amount) || 0);
    if (!accountId || magnitude <= 0) {
      setError("Choose an account and enter an amount greater than $0.");
      return;
    }
    try {
      await createTransaction.mutateAsync({
        account_id: accountId,
        category_id: categoryId || null,
        merchant_name: merchant,
        amount_minor: kind === "expense" ? -Math.round(magnitude * 100) : Math.round(magnitude * 100),
        txn_date: date,
      });
      setOpen(false);
      setMerchant("");
      setAmount("");
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't create that transaction."));
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm" />}>Add transaction</DialogTrigger>
      {open && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add transaction</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label>Account</Label>
              <Select value={accountId} onValueChange={(value) => setAccountId(value ?? "")}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose an account">
                    {() => accountOptions.find((a) => a.id === accountId)?.name}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {accountOptions.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="txn-merchant">Merchant</Label>
              <Input id="txn-merchant" required value={merchant} onChange={(e) => setMerchant(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Category (optional)</Label>
              <Select value={categoryId} onValueChange={(value) => setCategoryId(value ?? "")}>
                <SelectTrigger>
                  <SelectValue placeholder="Uncategorized">
                    {() => (categories ?? []).find((c) => c.id === categoryId)?.name}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {(categories ?? []).map((category) => (
                    <SelectItem key={category.id} value={category.id}>
                      {category.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label>Kind</Label>
                <Select value={kind} onValueChange={(v) => setKind(v as "expense" | "income")}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="expense">Expense</SelectItem>
                    <SelectItem value="income">Income</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="txn-amount">Amount</Label>
                <Input
                  id="txn-amount"
                  type="number"
                  min="0"
                  step="0.01"
                  required
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="txn-date">Date</Label>
                <Input id="txn-date" type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button type="submit" disabled={createTransaction.isPending}>
                {createTransaction.isPending ? "Adding…" : "Add transaction"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      )}
    </Dialog>
  );
}
