# DracoLatch: Test Resources & Authoritative Data

DracoLatch leverages the canonical U.S. Securities and Exchange Commission (SEC) EDGAR archive as its authoritative truth source.

---

## 1. Why SEC EDGAR is Suited for Intelligent Contract Escrow

- **Public & Sovereign:** The SEC publishes public company filings freely under federal transparency mandates, without requiring proprietary API keys or paid subscriptions.
- **Permanent Accession Identity:** Each filing submission receives a globally unique, immutable 18-digit Accession Number (e.g. `0001140361-25-025275`).
- **Deterministic Archive Paths:** Document URLs follow a predictable URL structure:
  `https://www.sec.gov/Archives/edgar/data/{CIK}/{ACCESSION_COMPACT}/{DOCUMENT}`
- **Tamper Evidence:** Filings cannot be modified retroactively without generating a separate amendment filing (e.g. `8-K/A`).

---

## 2. Mandatory Preflight: `DracoSourceProbe`

Before deploying the production `DracoLatch` custody contract, validators must execute the preflight probe:

1. Deploy `contracts/draco_source_probe.py` on the target network.
2. Call `probe_sec_endpoint`.
3. Verify that the finalized on-chain result is:
   `200:38298:79d278b5c34a40ec5618d5286c983120346ebb58ccd8587339533b88e7f22e37`

This confirms that network validators can fetch SEC endpoints and agree on exact byte counts and SHA-256 digests.

---

## 3. End-to-End Test Matrix

| Test Scenario | Verification Condition | Expected State Transition |
| :--- | :--- | :--- |
| **Commit-Reveal Claim** | Hunter commits hash; reveals valid accession & salt | `RESERVED` -> `CLAIMED` |
| **Happy Path Payout** | Authentic SEC filing satisfies locked disclosure requirement | `CLAIMED` -> `MATCH_PENDING` -> `PAID` |
| **Active Challenge** | Sponsor disputes `MATCH_PENDING` during challenge window | `MATCH_PENDING` -> `DISPUTED` |
| **Digest Mismatch** | Hunter submits incorrect SHA-256 digest | `UNRESOLVED / DIGEST_MISMATCH` |
| **Bounded Retry & Refund** | Retries exhausted after failure | `UNRESOLVED` (x2) -> `REFUNDED` |
| **Semantic Negative** | Valid filing with unrelated requirement | `NOT_MATCH / EVENT_MISMATCH` (Bounty reopens) |
| **Provenance Mismatch** | Document parameters missing from SEC index headers | `UNRESOLVED / PROVENANCE_MISMATCH` |
| **Model Contradiction** | Model outputs `MATCH` but sub-booleans fail | `UNRESOLVED / MODEL_CONTRADICTION` |
| **Accession Replay** | Reusing same accession for same bounty | Rejection: `ERR_ACCESSION_ALREADY_USED` |
| **Sponsor Self-Claim** | Sponsor attempts to claim own bounty | Rejection: `ERR_SPONSOR_CANNOT_CLAIM` |
| **Unauthorized Finalize** | Non-claimant calls `finalize_match` | Rejection: `ERR_ONLY_CLAIMANT_MAY_FINALIZE` |
| **Accounting Conservation** | Multi-bounty concurrent funding, payout, and refunds | Exact zero-drift balance invariant |
