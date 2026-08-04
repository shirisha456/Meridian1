"use client";

import { useState } from "react";

import { useAccounts } from "@/hooks/use-accounts";
import { useCreateHolding } from "@/hooks/use-investments";
import { apiErrorMessage } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function AddHoldingDialog() {
  const { data: accounts } = useAccounts();
  const createHolding = useCreateHolding();
  const investmentAccounts = (accounts?.items ?? []).filter((a) => a.type === "investment");

  const [open, setOpen] = useState(false);
  const [accountId, setAccountId] = useState("");
  const [symbol, setSymbol] = useState("");
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [costBasis, setCostBasis] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await createHolding.mutateAsync({
        account_id: accountId,
        symbol,
        name: name || undefined,
        quantity: Number.parseFloat(quantity) || 0,
        cost_basis_minor: Math.round((Number.parseFloat(costBasis) || 0) * 100),
      });
      setOpen(false);
      setSymbol("");
      setName("");
      setQuantity("");
      setCostBasis("");
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't add that holding."));
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm" />}>Add holding</DialogTrigger>
      {open && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add holding</DialogTitle>
          </DialogHeader>
          {investmentAccounts.length === 0 ? (
            <DialogDescription>
              You need an investment-type account first — add one from the Accounts page, then come back here.
            </DialogDescription>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label>Account</Label>
                <Select value={accountId} onValueChange={(value) => setAccountId(value ?? "")}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose an account">
                      {() => investmentAccounts.find((a) => a.id === accountId)?.name}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {investmentAccounts.map((account) => (
                      <SelectItem key={account.id} value={account.id}>
                        {account.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="holding-symbol">Symbol</Label>
                  <Input id="holding-symbol" required value={symbol} onChange={(e) => setSymbol(e.target.value)} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="holding-name">Name (optional)</Label>
                  <Input id="holding-name" value={name} onChange={(e) => setName(e.target.value)} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="holding-quantity">Quantity</Label>
                  <Input
                    id="holding-quantity"
                    type="number"
                    min="0.000001"
                    step="any"
                    required
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="holding-cost">Cost basis</Label>
                  <Input
                    id="holding-cost"
                    type="number"
                    min="0"
                    step="0.01"
                    required
                    value={costBasis}
                    onChange={(e) => setCostBasis(e.target.value)}
                  />
                </div>
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <DialogFooter>
                <Button type="submit" disabled={createHolding.isPending || !accountId}>
                  {createHolding.isPending ? "Adding…" : "Add holding"}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      )}
    </Dialog>
  );
}
