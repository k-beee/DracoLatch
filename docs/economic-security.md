# DracoLatch: Economic Security & Custody Invariants

DracoLatch acts as an autonomous financial latch that holds native GEN principal in escrow. Security is not merely access control: every state mutation must preserve strict custody liabilities, preventing loss of funds, unauthorized diversions, mempool frontrunning, replay attacks, or reentrancy.

---

## 1. Global Accounting Invariant

At any ledger height $H$, the contract's total locked principal must equal the exact sum of all active, unfinalized bounties:

$$\text{total\_locked} = \sum_{b \in \mathcal{B}_{\text{active}}} b.\text{locked\_wei}$$

- Every accepted `create_bounty` increases `total_locked` by exactly `gl.message.value`.
- Any invalid bounty creation returns the entire attached value to the sender immediately, creating zero liability.
- Exactly one terminal path decreases `total_locked` for a given bounty:
  1. **Match Finalization:** Moves `locked_wei` to `paid_wei` and emits a native transfer to the immutable submission claimant.
  2. **Sponsor Recovery:** Moves `locked_wei` to `refunded_wei` and emits a native transfer to the immutable bounty sponsor.
- Checks-Effects-Interactions (CEI) ensures that `locked_wei` is cleared to `0` and status is committed to storage before the external transfer is executed.

---

## 2. Frontrunning Protection: Commit-Reveal Claim Pattern

In naive disclosure contracts, hunters submit the filing accession number and expected content digest in plaintext. Because public SEC filings are visible to anyone once filed, malicious actors or MEV bots can monitor the mempool, copy the accession parameters, and frontrun the transaction with their own wallet.

DracoLatch mitigates this with a two-phase **Commit-Reveal Claim Protocol**:

1. **Commitment Phase (`commit_claim`):**
   $$\text{commitment} = \text{SHA256}(\text{claimant\_address} \parallel \text{accession} \parallel \text{salt})$$
   The hunter registers this commitment on-chain. This locks the claim slot to the hunter's address without revealing the SEC accession number.

2. **Reveal Phase (`reveal_and_submit`):**
   The hunter reveals `accession`, `primary_document`, `expected_sha256`, and `salt`.
   The contract verifies that:
   $$\text{SHA256}(\text{sender} \parallel \text{accession} \parallel \text{salt}) == \text{registered\_commitment}$$
   An attacker observing the reveal transaction cannot frontrun it because the commitment is bound to `claimant_address`.

---

## 3. Active Dispute & Challenge Mechanism

Unlike passive settlement windows that lack recourse, DracoLatch enforces a multi-block **Challenge Window** (`challenge_window`) following a `MATCH_PENDING` verdict:
- The Sponsor (or any third party posting a dispute bond) may call `challenge_match(submission_id, reason)`.
- Registering a dispute halts automatic finalization, marks the submission as `DISPUTED`, and requires secondary validator review or allows the sponsor to submit contradictory evidence.
- If no challenge is submitted before `challenge_deadline`, the claimant can call `finalize_match` to claim their reward.

---

## 4. Threat Matrix & Defense Controls

| Attack Vector | Defense Mechanism | Invariant Guaranteed |
| :--- | :--- | :--- |
| **Deployer Rugpull** | Zero admin keys; deployer address is not stored | Permissionless execution; no backdoor |
| **Mempool Frontrunning** | Commit-reveal scheme binds claim to caller address | Hunters cannot have discoveries stolen |
| **Sponsor Self-Claim** | Explicit check: `sender() != bounty.sponsor` | Sponsor cannot claim own bounty via same address |
| **Outsider Fund Redirection** | Payout recipient is fixed to `claimant` captured at claim | Payout cannot be redirected |
| **Double Payout / Refund** | `locked_wei` zeroed before transfer; terminal status | Terminal state is strictly one-way |
| **Accession Replay Attack** | `used_accessions[bounty_id:accession]` tracking | Same accession cannot be reused for same bounty |
| **Stale Revision Overwrite** | Method calls enforce `expected_revision == submission.revision` | Race conditions & out-of-order writes fail |
| **Document Spoofing** | URLs constructed directly from CIK + accession (no user URLs) | Phishing & malicious domain injection impossible |
| **Byte Tampering** | Exact SHA-256 preflight check before LLM evaluation | Manipulated bytes trigger `DIGEST_MISMATCH` |
| **Model Inconsistency** | Cross-field invariant: `MATCH` requires all 3 sub-booleans `True` | Contradictory model outputs fail closed |
| **Validator Divergence** | `gl.eq_principle.prompt_comparative` requires exact verdict & digest | Disagreements collapse to `UNRESOLVED` |
| **Reentrancy** | CEI pattern + EOA transfer interface | No callback execution path |
| **Spam Deposits** | `MIN_BOUNTY` threshold (0.001 GEN) with instant refund | Prevents dust state exhaustion |
