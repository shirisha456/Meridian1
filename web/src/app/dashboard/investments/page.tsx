"use client";

import { useState } from "react";
import axios from "axios";

import { useAddToWatchlist, useDeleteHolding, useHoldings, useRefreshPrices, useRemoveFromWatchlist, useWatchlist } from "@/hooks/use-investments";
import { apiErrorMessage } from "@/lib/api-client";
import { formatMinorUnits } from "@/lib/money";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AddHoldingDialog } from "@/components/dashboard/add-holding-dialog";

function priceCell(minor: number | null): string {
  return minor === null ? "No price yet" : formatMinorUnits(minor);
}

export default function InvestmentsPage() {
  const { data: holdingsPage, isLoading: holdingsLoading } = useHoldings();
  const { data: watchlist, isLoading: watchlistLoading } = useWatchlist();
  const deleteHolding = useDeleteHolding();
  const removeFromWatchlist = useRemoveFromWatchlist();
  const addToWatchlist = useAddToWatchlist();
  const refreshPrices = useRefreshPrices();

  const [symbol, setSymbol] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);

  const holdings = holdingsPage?.items ?? [];

  async function handleAddWatchlist(event: React.FormEvent) {
    event.preventDefault();
    if (!symbol.trim()) return;
    setError(null);
    try {
      await addToWatchlist.mutateAsync({ symbol: symbol.trim() });
      setSymbol("");
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't add that symbol."));
    }
  }

  async function handleRefreshPrices() {
    setError(null);
    setRefreshMessage(null);
    try {
      const updated = await refreshPrices.mutateAsync();
      setRefreshMessage(`Refreshed prices for ${updated.length} securit${updated.length === 1 ? "y" : "ies"}.`);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 503) {
        setError("Market data isn't configured for this environment.");
      } else {
        setError(apiErrorMessage(err, "Couldn't refresh prices."));
      }
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Investments</h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void handleRefreshPrices()} disabled={refreshPrices.isPending}>
            {refreshPrices.isPending ? "Refreshing…" : "Refresh prices"}
          </Button>
          <AddHoldingDialog />
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {refreshMessage && <p className="text-sm text-muted-foreground">{refreshMessage}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Holdings</CardTitle>
        </CardHeader>
        <CardContent>
          {holdingsLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : holdings.length === 0 ? (
            <p className="text-sm text-muted-foreground">No holdings yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Quantity</TableHead>
                  <TableHead>Cost basis</TableHead>
                  <TableHead>Latest price</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {holdings.map((holding) => (
                  <TableRow key={holding.id}>
                    <TableCell className="font-medium">{holding.security.symbol}</TableCell>
                    <TableCell>{holding.security.name}</TableCell>
                    <TableCell>{holding.quantity}</TableCell>
                    <TableCell>{formatMinorUnits(holding.cost_basis_minor)}</TableCell>
                    <TableCell>{priceCell(holding.security.latest_price_minor)}</TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void deleteHolding.mutateAsync(holding.id)}
                        disabled={deleteHolding.isPending}
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
        <CardHeader>
          <CardTitle>Watchlist</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <form onSubmit={handleAddWatchlist} className="flex gap-2">
            <Input
              placeholder="Symbol (e.g. AAPL)"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
            />
            <Button type="submit" size="sm" disabled={addToWatchlist.isPending}>
              Add
            </Button>
          </form>
          {watchlistLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : !watchlist || watchlist.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing on your watchlist yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {watchlist.map((item) => (
                <li key={item.id} className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm">
                  <span>
                    <span className="font-medium">{item.security.symbol}</span>{" "}
                    <span className="text-muted-foreground">{priceCell(item.security.latest_price_minor)}</span>
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void removeFromWatchlist.mutateAsync(item.id)}
                    disabled={removeFromWatchlist.isPending}
                  >
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
