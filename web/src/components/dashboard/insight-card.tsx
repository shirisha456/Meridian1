"use client";

import { useState } from "react";
import { SparklesIcon } from "lucide-react";

import { useGenerateInsight, useLatestInsight } from "@/hooks/use-insights";
import { apiErrorMessage } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function InsightCard() {
  const { data: insight, isLoading } = useLatestInsight();
  const generateInsight = useGenerateInsight();
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    setError(null);
    try {
      await generateInsight.mutateAsync(undefined);
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't generate an insight."));
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <SparklesIcon className="size-4" />
            Monthly insight
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="mt-2 h-4 w-3/4" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <SparklesIcon className="size-4" />
          Monthly insight
        </CardTitle>
        <Button size="sm" variant="outline" onClick={() => void handleGenerate()} disabled={generateInsight.isPending}>
          {generateInsight.isPending ? "Generating…" : "Generate"}
        </Button>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : insight ? (
          <p className="text-sm text-foreground">{insight.summary}</p>
        ) : (
          <p className="text-sm text-muted-foreground">
            No insight yet this period — click Generate for a summary of your spending.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
