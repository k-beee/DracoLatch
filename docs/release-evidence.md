# DracoLatch: Verification & Release Evidence Matrix

This document tracks local verification results and provides the execution protocol for on-chain deployment.

---

## 1. Local Automated Verification Results

| Check Category | Target Component | Status | Verification Command | Evidence Output |
| :--- | :--- | :--- | :--- | :--- |
| **Unit & Adversarial Suite** | `tests/test_draco_latch.py` | **PASS** | `pytest -v tests/test_draco_latch.py` | 14 passed in 0.02s (Commit-reveal, dispute, CEI, replay, conservation) |
| **Contract GenVM Linter** | `contracts/draco_latch.py` | **PASS** | `python3 -m genvm_linter.cli check contracts/draco_latch.py` | Lint passed (3 checks), Validation passed (13 methods: 4 view, 9 write) |
| **Probe GenVM Linter** | `contracts/draco_source_probe.py` | **PASS** | `python3 -m genvm_linter.cli check contracts/draco_source_probe.py` | Lint passed (3 checks), Validation passed (2 methods: 1 view, 1 write) |
| **Frontend Production Build** | `frontend/` | **PASS** | `npm run build` (tsc + vite) | Vite production bundle completed with zero errors in 879ms |
| **Full Pipeline Script** | `./scripts/verify_local.sh` | **PASS** | `./scripts/verify_local.sh` | All pipeline steps exit with code 0 |

---

## 2. On-Chain Deployment Protocol (Studio Net / Studio Next)

### Preflight Verification:
1. Deploy `DracoSourceProbe` (`contracts/draco_source_probe.py`).
2. Call `probe_sec_endpoint`.
3. Confirm consensus on:
   ```text
   200:38298:79d278b5c34a40ec5618d5286c983120346ebb58ccd8587339533b88e7f22e37
   ```

### Custody Contract Deployment:
1. Deploy `DracoLatch` (`contracts/draco_latch.py`) without constructor parameters.
2. Confirm zero privileged roles or admin backdoors.
3. Update `frontend/.env` with the deployed contract address.
4. Record deployment transaction hash and explorer address URL.

---

## 3. Recommended Multi-Lifecycle Test Cases

### Lifecycle A: Happy Path with Commit-Reveal
1. **Sponsor:** `create_bounty` with 0.01 GEN deposit. (State: `OPEN`)
2. **Hunter:** Compute `sha256(claimant + accession + salt)` and call `commit_claim`. (State: `RESERVED`)
3. **Hunter:** Call `reveal_and_submit` with accession, document name, digest, and salt. (State: `CLAIMED`)
4. **Sponsor/Hunter:** Call `assess_submission`. (State: `MATCH_PENDING`, Challenge Deadline set)
5. **Hunter:** After challenge window passes, call `finalize_match`. (State: `PAID`, 0.01 GEN disbursed to claimant)

### Lifecycle B: Active Challenge & Dispute Path
1. Steps 1–4 from Lifecycle A.
2. **Sponsor:** During the open challenge window, call `challenge_match(submission_id, "Omitted material clause")`.
3. Verify that submission state transitions to `DISPUTED`.
4. Verify that claimant attempts to `finalize_match` fail closed.

### Lifecycle C: Digest Failure, Bounded Retry, and Sponsor Recovery
1. **Sponsor:** `create_bounty` with 0.01 GEN deposit. (State: `OPEN`)
2. **Hunter:** Call `submit_direct` with intentionally incorrect SHA-256 digest. (State: `CLAIMED`)
3. **Sponsor:** Call `assess_submission`. (State: `UNRESOLVED / DIGEST_MISMATCH`)
4. **Hunter/Sponsor:** Call `retry_unresolved`. (State: `CLAIMED`, attempt 1)
5. **Sponsor:** Call `assess_submission`. (State: `UNRESOLVED / DIGEST_MISMATCH`, max retries reached)
6. **Sponsor:** Call `recover_bounty`. (State: `REFUNDED`, 0.01 GEN returned to sponsor)
