"use client";

import { useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import axios from "axios";

import { useCreateLinkToken, useLinkInstitution } from "@/hooks/use-institutions";
import { Button } from "@/components/ui/button";

export function ConnectBankButton() {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const createLinkToken = useCreateLinkToken();
  const linkInstitution = useLinkInstitution();

  const { open, ready } = usePlaidLink({
    token: linkToken ?? "",
    onSuccess: (publicToken, metadata) => {
      if (!publicToken) return;
      void linkInstitution.mutateAsync({
        public_token: publicToken,
        institution_id: metadata.institution?.institution_id ?? undefined,
        institution_name: metadata.institution?.name ?? "Bank",
      });
    },
  });

  useEffect(() => {
    if (linkToken && ready) {
      open();
    }
  }, [linkToken, ready, open]);

  async function handleClick() {
    setError(null);
    try {
      const { link_token } = await createLinkToken.mutateAsync();
      setLinkToken(link_token);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 503) {
        setError("Plaid isn't configured for this environment.");
      } else {
        setError("Couldn't start bank linking.");
      }
    }
  }

  return (
    <div className="flex flex-col items-end gap-1.5">
      <Button size="sm" variant="outline" onClick={() => void handleClick()} disabled={createLinkToken.isPending}>
        Connect a bank
      </Button>
      {error && <p className="max-w-64 text-right text-xs text-destructive">{error}</p>}
    </div>
  );
}
