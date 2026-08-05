"use client";

import { useState } from "react";

import { useForecast } from "@/hooks/use-forecast";
import { cn } from "@/lib/utils";
import { formatMinorUnits } from "@/lib/money";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ForecastChart } from "@/components/dashboard/forecast-chart";

const HORIZON_OPTIONS = [30, 60, 90] as const;

export default function ForecastPage() {
  const [horizonDays, setHorizonDays] = useState<(typeof HORIZON_OPTIONS)[number]>(30);
  const { data: forecast, isLoading } = useForecast(horizonDays);

  const dipsBelowZero = forecast?.daily_projection.some((point) => point.projected_balance_minor < 0) ?? false;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Cash-Flow Forecast</h1>
          <p className="text-sm text-muted-foreground">
            Projects your checking/savings/cash balance forward from real recurring transactions — merchants
            that have shown up at least 3 times recently. Not a guess: every line below is grounded in your
            actual transaction history.
          </p>
        </div>
        <div className="flex gap-1">
          {HORIZON_OPTIONS.map((option) => (
            <Button
              key={option}
              size="sm"
              variant={horizonDays === option ? "default" : "outline"}
              onClick={() => setHorizonDays(option)}
            >
              {option}d
            </Button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : forecast ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">Starting balance</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">
                {formatMinorUnits(forecast.starting_balance_minor)}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Projected in {horizonDays} days
                </CardTitle>
              </CardHeader>
              <CardContent
                className={cn(
                  "text-2xl font-semibold",
                  forecast.projected_ending_balance_minor < 0 && "text-destructive",
                )}
              >
                {formatMinorUnits(forecast.projected_ending_balance_minor)}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">Recurring items found</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold">{forecast.recurring_items.length}</CardContent>
            </Card>
          </div>

          {dipsBelowZero && (
            <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              Your projected balance dips below zero within this window based on known recurring activity.
            </p>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Projected balance</CardTitle>
            </CardHeader>
            <CardContent>
              <ForecastChart points={forecast.daily_projection} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Detected recurring transactions</CardTitle>
            </CardHeader>
            <CardContent>
              {forecast.recurring_items.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No recurring merchants detected yet — a merchant needs to show up at least 3 times in the
                  last 120 days to be picked up.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Merchant</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Every</TableHead>
                      <TableHead>Next expected</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {forecast.recurring_items.map((item) => (
                      <TableRow key={item.merchant_name}>
                        <TableCell className="font-medium">{item.merchant_name}</TableCell>
                        <TableCell>{item.category_name ?? "Uncategorized"}</TableCell>
                        <TableCell className={item.average_amount_minor < 0 ? "text-destructive" : "text-emerald-600"}>
                          {formatMinorUnits(item.average_amount_minor)}
                        </TableCell>
                        <TableCell>~{Math.round(item.average_interval_days)} days</TableCell>
                        <TableCell>{item.next_expected_date}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
