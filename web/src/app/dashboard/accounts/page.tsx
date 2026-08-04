"use client";

import { useState } from "react";

import { useAccounts, useDeleteAccount } from "@/hooks/use-accounts";
import { useInstitutions, useSyncInstitution, useUnlinkInstitution } from "@/hooks/use-institutions";
import { formatMinorUnits } from "@/lib/money";
import type { InstitutionStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AddAccountDialog } from "@/components/dashboard/add-account-dialog";
import { ConnectBankButton } from "@/components/dashboard/connect-bank-button";

const STATUS_VARIANT: Record<InstitutionStatus, "secondary" | "destructive"> = {
  active: "secondary",
  error: "destructive",
  revoked: "destructive",
};

const STATUS_LABEL: Record<InstitutionStatus, string> = {
  active: "Active",
  error: "Sync error",
  revoked: "Needs re-auth",
};

export default function AccountsPage() {
  const { data: accountsPage, isLoading } = useAccounts();
  const deleteAccount = useDeleteAccount();
  const { data: institutions, isLoading: institutionsLoading } = useInstitutions();
  const syncInstitution = useSyncInstitution();
  const unlinkInstitution = useUnlinkInstitution();
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const accounts = accountsPage?.items ?? [];

  async function handleSync(id: string) {
    setSyncingId(id);
    try {
      await syncInstitution.mutateAsync(id);
    } finally {
      setSyncingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Accounts</h1>
        <AddAccountDialog />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Your accounts</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : accounts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No accounts yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Currency</TableHead>
                  <TableHead>Balance</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.map((account) => (
                  <TableRow key={account.id}>
                    <TableCell className="font-medium">{account.name}</TableCell>
                    <TableCell className="capitalize">{account.type}</TableCell>
                    <TableCell>{account.currency}</TableCell>
                    <TableCell>{formatMinorUnits(account.current_balance_minor, account.currency)}</TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void deleteAccount.mutateAsync(account.id)}
                        disabled={deleteAccount.isPending}
                      >
                        Remove
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Linked institutions</CardTitle>
          <ConnectBankButton />
        </CardHeader>
        <CardContent>
          {institutionsLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : !institutions || institutions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No banks linked yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {institutions.map((institution) => (
                <li
                  key={institution.id}
                  className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{institution.name}</span>
                    <Badge variant={STATUS_VARIANT[institution.status]}>{STATUS_LABEL[institution.status]}</Badge>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handleSync(institution.id)}
                      disabled={syncingId === institution.id}
                    >
                      {syncingId === institution.id ? "Syncing…" : "Sync"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => void unlinkInstitution.mutateAsync(institution.id)}
                      disabled={unlinkInstitution.isPending}
                    >
                      Unlink
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
