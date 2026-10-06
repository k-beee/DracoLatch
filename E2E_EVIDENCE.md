# DracoLatch End-to-End Verification & Deployment Evidence

This document provides live on-chain deployment records, contract source verification, and reproducible execution evidence for **DracoLatch**.

---

## 1. Verified Live Deployment

| Property | Value |
| :--- | :--- |
| **Protocol Name** | `DracoLatch` |
| **Network** | GenLayer Studio Next (Chain `61997`) |
| **Deployed Contract** | [`0x378640F3dbfC35F162945D12B73234138e211Bb6`](https://explorer-studio-next.genlayer.com/address/0x378640F3dbfC35F162945D12B73234138e211Bb6) |
| **Source Byte Parity** | **100% Byte-for-Byte Match** against `contracts/draco_latch.py` (Verified via JSON-RPC) |
| **GenVM Linter Status** | **PASS** (3/3 checks passed, 13 methods: 4 view, 9 write) |
| **Source Authority** | U.S. Securities and Exchange Commission (SEC) EDGAR Archive |
| **Diagnostic Probe** | [`0x60d3f54658b15b07F29f08103317324a876CF638`](https://explorer-studio-next.genlayer.com/address/0x60d3f54658b15b07F29f08103317324a876CF638) |

The contract constructor requires zero arguments and stores no privileged deployer address. All roles are derived permissionlessly per bounty: the funding wallet becomes that bounty's Sponsor, and any different address can submit a claim.

---

## 2. On-Chain Introspection & Test Transaction Evidence

### Verified Live Test Transaction (`create_bounty`)
- **Transaction Hash:** [`0x79e594f22db1ff34576d44cf4e368b35696c6b23bfad5a22ed22eb75b9d1dea9`](https://explorer-studio-next.genlayer.com/tx/0x79e594f22db1ff34576d44cf4e368b35696c6b23bfad5a22ed22eb75b9d1dea9)
- **Sender Address:** `0xadF532d180D50F4F71a39A909FEa1F941BfC8a45`
- **Contract Address:** [`0x378640F3dbfC35F162945D12B73234138e211Bb6`](https://explorer-studio-next.genlayer.com/address/0x378640F3dbfC35F162945D12B73234138e211Bb6)
- **Value Escrowed:** `0.01 GEN` (`10000000000000000 wei`)
- **Consensus Result:** `MAJORITY_AGREE` (Round 0, 5/5 validator votes committed/revealed)
- **Lifecycle State:** `FINALIZED` (Accepted)

### Live Query Responses (RPC Verified)

**Contract Totals (`get_totals()`):**
```json
{
  "bounties": 1,
  "locked_wei": "10000000000000000",
  "paid_wei": "0",
  "refunded_wei": "0",
  "submissions": 0
}
```

**Bounty #1 State (`get_bounty(1)`):**
```json
{
  "id": 1,
  "title": "SEC 8-K Succession Bounty (Studio Next Test)",
  "requirement": "Confirm Apple planned executive succession and transition duties on Form 8-K.",
  "sponsor": "0xadf532d180d50f4f71a39a909fea1f941bfc8a45",
  "status": "OPEN",
  "locked_wei": "10000000000000000",
  "cik": "0000320193",
  "allowed_form": "8-K",
  "filing_start": 1700000000,
  "filing_end": 1800000000,
  "challenge_window": 300,
  "active_submission": 0,
  "created_at": 1790441554,
  "submission_deadline": 1790527954
}
```


---

## 3. End-to-End Operational Lifecycle Matrix

Reviewers can execute and audit three distinct live lifecycles using any two distinct wallets (Sponsor & Hunter):

### Path A: Happy Path with Commit-Reveal & Payout
1. **Sponsor:** Calls `create_bounty` with attached native GEN value ($\ge 0.001$ GEN). State becomes `OPEN`.
2. **Hunter:** Generates `commitment = sha256(claimant + accession + salt)` and calls `commit_claim`. State becomes `RESERVED`, preventing mempool frontrunning.
3. **Hunter:** Calls `reveal_and_submit` with accession, document name, expected digest, and salt. State becomes `CLAIMED`.
4. **Sponsor / Hunter:** Calls `assess_submission`. Validators fetch SEC archive, verify byte digest preflight, evaluate natural language conditions, and reach `MATCH_PENDING` comparative consensus.
5. **Hunter:** After the challenge window lapses, calls `finalize_match`. Contract transfers locked GEN directly to claimant and commits `PAID`.

### Path B: Active Challenge, Appellate Adjudication & Dual Settlement Paths
1. Steps 1–4 from Path A (Bounty created, evidence submitted, `MATCH_PENDING` reached).
2. **Sponsor:** During the open challenge window, calls `challenge_match(submission_id, "Omitted material duties")`.
3. Contract immediately transitions to `DISPUTED`, halting automated payout and opening the adjudication phase.
4. **Appellate Adjudication (`adjudicate_dispute`)**: Validators independently re-verify the filing against the locked requirement and sponsor allegations.
   - **Outcome B1 (Challenge Dismissed / Hunter Payout):** Validators rule `DISMISS_CHALLENGE`. State transitions to `MATCH_UPHELD`. Claimant calls `finalize_match`. Contract transfers 100% of escrowed principal to claimant (`PAID`).
   - **Outcome B2 (Challenge Upheld / Sponsor Recovery):** Validators rule `UPHOLD_CHALLENGE`. State transitions to `CHALLENGE_UPHELD`. Sponsor calls `recover_bounty`. Contract returns 100% of escrowed principal to sponsor (`REFUNDED`).
   - **Outcome B3 (Voluntary Withdrawal):** Sponsor calls `withdraw_challenge`. State transitions to `MATCH_UPHELD`. Claimant finalizes payout (`PAID`).
   - **Outcome B4 (Anti-Deadlock Abandonment Fallback):** If sponsor files a challenge and abandons it without adjudication beyond the dispute deadline, claimant calls `finalize_match` (`PAID`).

### Path C: Digest Mismatch, Bounded Retries, and Sponsor Recovery
1. **Sponsor:** Calls `create_bounty` with attached GEN value.
2. **Hunter:** Submits an invalid or corrupted SHA-256 digest via `submit_direct`.
3. **Sponsor:** Calls `assess_submission`. Fails closed as `UNRESOLVED / DIGEST_MISMATCH`.
4. **Sponsor / Hunter:** Calls `retry_unresolved` up to `MAX_ASSESSMENT_RETRIES` (2 attempts).
5. **Sponsor:** Calls `recover_bounty`. Contract returns 100% of escrowed principal to sponsor and commits `REFUNDED`.

---

## 4. Local Test & Static Analysis Evidence

All 20 unit and adversarial tests pass in 0.02s:

```text
tests/test_draco_latch.py::test_permissionless_sponsor_and_self_claim_guard PASSED
tests/test_draco_latch.py::test_commit_reveal_claim_flow_and_anti_frontrunning PASSED
tests/test_draco_latch.py::test_commit_reveal_expiry_and_salt_mismatch PASSED
tests/test_draco_latch.py::test_happy_path_real_custody_and_payout PASSED
tests/test_draco_latch.py::test_active_dispute_challenge_mechanism PASSED
tests/test_draco_latch.py::test_digest_mismatch_retries_and_sponsor_recovery PASSED
tests/test_draco_latch.py::test_semantic_not_match_reopens_bounty_and_blocks_accession_replay PASSED
tests/test_draco_latch.py::test_metadata_provenance_failure_fails_closed PASSED
tests/test_draco_latch.py::test_model_contradiction_fails_closed PASSED
tests/test_draco_latch.py::test_consensus_divergence_fails_closed PASSED
tests/test_draco_latch.py::test_outsider_cannot_grief_assessment_or_retry_budget PASSED
tests/test_draco_latch.py::test_invalid_payable_inputs_are_immediately_refunded PASSED
tests/test_draco_latch.py::test_economic_conservation_across_independent_bounties PASSED
tests/test_draco_latch.py::test_html_tag_stripping_and_sanitization PASSED
tests/test_draco_latch.py::test_active_commit_reserves_slot_against_direct_submission PASSED
tests/test_draco_latch.py::test_expired_commit_releases_slot_for_direct_submission PASSED
tests/test_draco_latch.py::test_dispute_adjudication_dismisses_challenge_and_settles_hunter_payout PASSED
tests/test_draco_latch.py::test_dispute_adjudication_upholds_challenge_and_authorizes_sponsor_recovery PASSED
tests/test_draco_latch.py::test_dispute_sponsor_withdraw_challenge_and_hunter_payout PASSED
tests/test_draco_latch.py::test_dispute_timeout_abandonment_settles_hunter PASSED

============================== 20 passed in 0.02s ==============================
```
