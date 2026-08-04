"use client";

import { useState } from "react";

import { useCreateAccount } from "@/hooks/use-accounts";
import { apiErrorMessage } from "@/lib/api-client";
import type { AccountType } from "@/lib/types";
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

const ACCOUNT_TYPES: AccountType[] = ["checking", "savings", "credit", "investment", "loan", "cash"];
const CURRENCIES = ["USD", "EUR", "GBP", "CAD"];

export function AddAccountDialog() {
  const createAccount = useCreateAccount();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState<AccountType>("checking");
  const [currency, setCurrency] = useState("USD");
  const [balance, setBalance] = useState("0");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await createAccount.mutateAsync({
        name,
        type,
        currency,
        current_balance_minor: Math.round((Number.parseFloat(balance) || 0) * 100),
      });
      setOpen(false);
      setName("");
      setBalance("0");
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't create that account."));
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm" />}>Add account</DialogTrigger>
      {open && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add account</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="account-name">Name</Label>
              <Input id="account-name" required value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Type</Label>
              <Select value={type} onValueChange={(value) => setType(value as AccountType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ACCOUNT_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label>Currency</Label>
                <Select value={currency} onValueChange={(value) => setCurrency(value ?? "USD")}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CURRENCIES.map((c) => (
                      <SelectItem key={c} value={c}>
                        {c}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="account-balance">Starting balance</Label>
                <Input
                  id="account-balance"
                  type="number"
                  step="0.01"
                  value={balance}
                  onChange={(e) => setBalance(e.target.value)}
                />
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button type="submit" disabled={createAccount.isPending}>
                {createAccount.isPending ? "Adding…" : "Add account"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      )}
    </Dialog>
  );
}
