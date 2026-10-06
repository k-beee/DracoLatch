# DracoLatch API & Contract Reference

Complete specification of public methods, data structures, and invariants for `DracoLatch`.

---

## Data Structures

### `BountyRecord` (JSON Serialized)
```json
{
  "id": 1,
  "sponsor": "0x1111...1111",
  "title": "Apple COO Succession Disclosure",
  "requirement": "Confirm a planned COO succession...",
  "cik": "0000320193",
  "allowed_form": "8-K",
  "filing_start": 1700000000,
  "filing_end": 1800000000,
  "submission_deadline": 1790320562,
  "challenge_window": 300,
  "status": "OPEN",
  "locked_wei": 10000000000000000,
  "active_submission": 0,
  "created_at": 1790234162
}
```

### `SubmissionRecord` (JSON Serialized)
```json
{
  "id": 1,
  "bounty_id": 1,
  "claimant": "0x2222...2222",
  "accession": "0001140361-25-025275",
  "primary_document": "ef20051741_8k.htm",
  "expected_sha256": "79d278b5c34a40ec5618d5286c983120346ebb58ccd8587339533b88e7f22e37",
  "status": "CLAIMED",
  "reason": "NOT_ASSESSED",
  "attempts": 0,
  "evidence_digest": "",
  "verdict_digest": "",
  "challenge_deadline": 0,
  "revision": 1
}
```

---

## Write Methods

### `create_bounty`
- **Decorator:** `@gl.public.write.payable`
- **Parameters:**
  - `title: str` (5–100 chars)
  - `requirement: str` (40–1200 chars)
  - `cik: str` (10-digit zero-padded SEC Central Index Key)
  - `allowed_form: str` (e.g. `8-K`, `10-Q`, `10-K`)
  - `filing_start: u256` (Unix timestamp lower bound)
  - `filing_end: u256` (Unix timestamp upper bound)
  - `submission_window_sec: u256` (3600 to 2,592,000 seconds)
  - `challenge_window_sec: u256` (300 to 604,800 seconds)
- **Payable Value:** Must be $\ge 10^{15}$ wei (0.001 GEN). Attached value refunded on validation failure.
- **Returns:** `u256` Bounty ID or error string.

### `commit_claim`
- **Decorator:** `@gl.public.write`
- **Parameters:**
  - `bounty_id: u256`
  - `commitment_hash: str` (64-character lowercase hex of `sha256(claimant + accession + salt)`)
- **Returns:** `"COMMITMENT_RECORDED"` or error string.

### `reveal_and_submit`
- **Decorator:** `@gl.public.write`
- **Parameters:**
  - `bounty_id: u256`
  - `accession: str` (Format: `0000000000-00-000000`)
  - `primary_document: str` (Ends with `.htm`, `.html`, or `.txt`)
  - `expected_sha256: str` (64 hex characters)
  - `salt: str` (Secret hunter salt)
- **Returns:** `u256` Submission ID or error string.

### `challenge_match`
- **Decorator:** `@gl.public.write`
- **Parameters:**
  - `submission_id: u256`
  - `dispute_reason: str` (Max 100 chars)
- **Permission:** Sponsor only.
- **Condition:** Submission must be in `MATCH_PENDING` status prior to `challenge_deadline`.
- **Returns:** `"DISPUTED"` or error string.

### `adjudicate_dispute`
- **Decorator:** `@gl.public.write`
- **Parameters:**
  - `submission_id: u256`
  - `expected_revision: u256`
- **Permission:** Sponsor or Submission Claimant.
- **Condition:** Submission and Bounty must be in `DISPUTED` status.
- **Effects:** Multi-validator appellate consensus evaluates filing against locked requirements and sponsor allegations:
  - If `DISMISS_CHALLENGE`: Transitions to `MATCH_UPHELD`, authorizing Claimant to finalize payout.
  - If `UPHOLD_CHALLENGE`: Transitions to `CHALLENGE_UPHELD`, authorizing Sponsor to recover escrowed capital.
- **Returns:** Status string (`MATCH_UPHELD`, `CHALLENGE_UPHELD`, or `UNRESOLVED`).

### `withdraw_challenge`
- **Decorator:** `@gl.public.write`
- **Parameters:** `submission_id: u256`
- **Permission:** Sponsor only.
- **Condition:** Submission and Bounty in `DISPUTED` status.
- **Effects:** Voluntarily dismisses challenge, transitions to `MATCH_UPHELD`, unlocks immediate finalization.
- **Returns:** `"MATCH_UPHELD"` or error string.

### `finalize_match`
- **Decorator:** `@gl.public.write`
- **Parameters:** `submission_id: u256`
- **Permission:** Submission claimant only.
- **Conditions (any of the following):**
  1. `s.status == MATCH_PENDING` and `now() > challenge_deadline` (Challenge window lapsed without dispute).
  2. `s.status == MATCH_UPHELD` (Dispute adjudicated in hunter's favor, or challenge voluntarily withdrawn).
  3. `s.status == DISPUTED` and `now() > dispute_deadline` (Anti-deadlock fallback if sponsor abandons challenge).
- **Effects:** Clears `locked_wei = 0`, sets `PAID`, transfers GEN to claimant.
- **Returns:** `"PAID"` or error string.

### `recover_bounty`
- **Decorator:** `@gl.public.write`
- **Parameters:** `bounty_id: u256`
- **Permission:** Bounty sponsor only.
- **Conditions (any of the following):**
  1. Bounty in `OPEN` past `submission_deadline`.
  2. Active submission exhausted retries in `UNRESOLVED`.
  3. Bounty in `CHALLENGE_UPHELD` (Dispute adjudicated in sponsor's favor).
- **Effects:** Clears `locked_wei = 0`, sets `REFUNDED`, returns GEN to sponsor.
- **Returns:** `"REFUNDED"` or error string.

