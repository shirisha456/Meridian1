# ADR-0003: Fernet as a local stand-in for AWS KMS envelope encryption

## Status

Accepted

## Context

Plaid access tokens are bearer credentials: anyone who has one can pull a
user's transaction history from their bank until the token is revoked.
They must be encrypted at rest, not stored as plaintext in
`institutions.access_token_ciphertext`. A real production deployment
would use AWS KMS envelope encryption — a per-record data key generated
by KMS, itself encrypted by a KMS master key that never leaves AWS, with
every decrypt call audit-logged and individually revocable via IAM. This
project has no AWS account provisioned to test against (see
[ADR-0010, once written in Phase 14](../phase14.md)), so it needs a local
substitute that's honest about what it does and doesn't provide.

## Decision

Use `cryptography.fernet.Fernet` keyed by a single static key from the
`ENCRYPTION_KEY` environment variable. `app/core/encryption.py` exposes
exactly two functions — `encrypt(plaintext) -> bytes` and
`decrypt(ciphertext) -> str` — matching the call shape a real KMS-backed
implementation would have, so swapping one in later only touches this
one module; no caller (`app/institutions/service.py`) needs to change.

## Alternatives considered

- **Plaintext storage** — rejected outright; a leaked database backup
  would hand over every linked bank's transaction history directly.
- **A real KMS integration now** — rejected for this phase: it requires
  an AWS account, IAM setup, and ongoing cost this project doesn't have
  provisioned yet. Terraform for the real KMS key is planned for
  Phase 14, written and validated but not applied — consistent with the
  rest of this project's honest "designed for, not deployed to" AWS
  story.

## Consequences

- Real: ciphertext is genuinely on disk, never plaintext. A database
  dump alone does not expose Plaid access tokens.
- Real gap: one leaked `ENCRYPTION_KEY` decrypts every stored token for
  every user, all at once. KMS envelope encryption limits blast radius
  per record and makes each decrypt individually revocable and
  audit-logged; this stand-in provides neither.
- `ENCRYPTION_KEY` must be a real, securely-generated value in any
  environment where institutions get linked — the empty-string default
  is intentional (the app boots and every non-Plaid feature works
  without it) but `EncryptionNotConfigured` (503) is what a caller gets
  if they try to link an institution without setting it. There's no
  runtime guard against a *weak* (non-empty but low-entropy) key the way
  there is for `JWT_SECRET`, since Fernet keys aren't human-chosen
  strings — get one from `Fernet.generate_key()`, not by inventing one.

## Validation

`apps/core-api/tests/test_encryption.py` covers round-trip
encrypt/decrypt, that ciphertext is never equal to the plaintext, and
that `EncryptionNotConfigured` is raised (not a bare crash) when
`ENCRYPTION_KEY` is unset. `apps/core-api/tests/test_institutions.py`
confirms `access_token_ciphertext` never appears in any API response —
only the encrypted bytes exist in the database, and even those are never
serialized back to a client.
