"use client";

import { useState } from "react";

import { useNetWorthHistory, useRecomputeNetWorth } from "@/hooks/use-networth";
import { apiErrorMessage } from "@/lib/api-client";
import { formatMinorUnits } from "@/lib/money";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { NetWorthChart } from "@/components/dashboard/net-worth-chart";

export default function NetWorthPage() {
  const { data: snapshots, isLoading } = useNetWorthHistory();
  const recompute = useRecomputeNetWorth();
  const [error, setError] = useState<string | null>(null);

  async function handleRecompute() {
    setError(null);
    try {
      await recompute.mutateAsync();
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't recompute net worth."));
    }
  }

  const sorted = [...(snapshots ?? [])].sort((a, b) => b.snapshot_date.localeCompare(a.snapshot_date));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Net Worth</h1>
          <p className="text-sm text-muted-foreground">
            This page reads the latest daily snapshot, not a live recomputation — use &ldquo;Recompute
            now&rdquo; to refresh it.
          </p>
        </div>
        <Button size="sm" onClick={() => void handleRecompute()} disabled={recompute.isPending}>
          {recompute.isPending ? "Recomputing…" : "Recompute now"}
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <NetWorthChart snapshots={sorted} />
          )}
        </CardContent>
      </Card>

      {!isLoading && sorted.length > 0 && (
        <Card>
          <CardContent className="pt-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Assets</TableHead>
                  <TableHead>Liabilities</TableHead>
                  <TableHead>Net worth</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((snapshot) => (
                  <TableRow key={snapshot.id}>
                    <TableCell>{snapshot.snapshot_date}</TableCell>
                    <TableCell>{formatMinorUnits(snapshot.assets_minor)}</TableCell>
                    <TableCell>{formatMinorUnits(snapshot.liabilities_minor)}</TableCell>
                    <TableCell className="font-medium">{formatMinorUnits(snapshot.net_worth_minor)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
