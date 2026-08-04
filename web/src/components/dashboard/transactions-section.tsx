"use client";

import { useMemo, useState } from "react";
import { SearchIcon } from "lucide-react";

import { useAccounts } from "@/hooks/use-accounts";
import { useCategories } from "@/hooks/use-categories";
import { useDeleteTransaction, useTransactions } from "@/hooks/use-transactions";
import { formatMinorUnits } from "@/lib/money";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AddTransactionDialog } from "@/components/dashboard/add-transaction-dialog";

const PAGE_SIZE = 10;

export function TransactionsSection() {
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const { data: accounts } = useAccounts();
  const { data: categories } = useCategories();
  const { data, isLoading } = useTransactions({ q: search || undefined, limit: PAGE_SIZE, offset });
  const deleteTransaction = useDeleteTransaction();

  const accountNameById = useMemo(
    () => new Map((accounts?.items ?? []).map((a) => [a.id, a.name])),
    [accounts],
  );
  const categoryNameById = useMemo(
    () => new Map((categories ?? []).map((c) => [c.id, c.name])),
    [categories],
  );

  const transactions = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasNext = offset + PAGE_SIZE < total;
  const hasPrev = offset > 0;

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Transactions</h2>
        <div className="flex items-center gap-2">
          <div className="relative">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search merchant…"
              className="w-48 pl-7"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
            />
          </div>
          <AddTransactionDialog />
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : transactions.length === 0 ? (
        <p className="text-sm text-muted-foreground">No transactions yet.</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Merchant</TableHead>
                <TableHead>Account</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {transactions.map((txn) => (
                <TableRow key={txn.id}>
                  <TableCell>{txn.txn_date}</TableCell>
                  <TableCell>{txn.merchant_name}</TableCell>
                  <TableCell>{accountNameById.get(txn.account_id) ?? "—"}</TableCell>
                  <TableCell>{txn.category_id ? (categoryNameById.get(txn.category_id) ?? "—") : "Uncategorized"}</TableCell>
                  <TableCell className={txn.amount_minor < 0 ? "text-destructive" : "text-foreground"}>
                    {formatMinorUnits(txn.amount_minor, txn.currency)}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => void deleteTransaction.mutateAsync(txn.id)}
                      disabled={deleteTransaction.isPending}
                    >
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={!hasPrev} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
                Previous
              </Button>
              <Button variant="outline" size="sm" disabled={!hasNext} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
