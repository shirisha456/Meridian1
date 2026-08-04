"use client";

import Link from "next/link";

import { useAccounts } from "@/hooks/use-accounts";
import { formatMinorUnits } from "@/lib/money";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AddAccountDialog } from "@/components/dashboard/add-account-dialog";

export function AccountsSection() {
  const { data, isLoading } = useAccounts();
  const accounts = data?.items ?? [];

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Accounts</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" nativeButton={false} render={<Link href="/dashboard/accounts" />}>
            Manage
          </Button>
          <AddAccountDialog />
        </div>
      </div>
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : accounts.length === 0 ? (
        <p className="text-sm text-muted-foreground">No accounts yet — add one to get started.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {accounts.map((account) => (
            <Card key={account.id}>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>{account.name}</span>
                  <span className="text-xs font-normal text-muted-foreground capitalize">{account.type}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xl font-semibold">{formatMinorUnits(account.current_balance_minor, account.currency)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}
