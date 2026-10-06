"""
DracoLatch Comprehensive Unit & Adversarial Test Suite.
Simulates the GenLayer Python SDK runtime and verifies:
- Permissionless per-bounty roles and self-claim rejection
- Cryptographic Commit-Reveal claim protocol and anti-frontrunning
- Full happy-path custody and payout settlement
- Active dispute and challenge mechanism
- SHA-256 preflight mismatch, bounded retries, and sponsor recovery
- Semantic NOT_MATCH reopening and accession replay defense
- Metadata provenance failure fail-closed behavior
- Cross-field model contradiction fail-closed behavior
- Consensus divergence fail-closed behavior
- Outsider griefing protection on assessment budget
- Automatic refund on invalid payable bounty deposits
- Multi-bounty economic conservation
- Content sanitization and HTML tag stripping
"""

from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import typing
import pytest

# Test Addresses
SPONSOR = "0x1111111111111111111111111111111111111111"
CLAIMANT = "0x2222222222222222222222222222222222222222"
OUTSIDER = "0x3333333333333333333333333333333333333333"

# Simulated GenLayer Runtime Primitives
class TreeMap(dict):
    @classmethod
    def __class_getitem__(cls, _):
        return cls

class U256(int):
    pass

class ContractBase:
    def __init_subclass__(cls, **kw):
        original = cls.__dict__.get("__init__")
        def init(self, *args, **kwargs):
            for name, kind in cls.__annotations__.items():
                if kind is TreeMap:
                    setattr(self, name, TreeMap())
            if original:
                original(self, *args, **kwargs)
        cls.__init__ = init

class Write:
    def __call__(self, fn): return fn
    def payable(self, fn): return fn

class Public:
    write = Write()
    view = staticmethod(lambda fn: fn)

class WebResponse:
    def __init__(self, status: int, body: typing.Union[bytes, str]):
        self.status = status
        self.body = body if isinstance(body, bytes) else body.encode("utf-8")

class MockNondet:
    def __init__(self):
        self.responses = {}
        self.default_model_output = {
            "verdict": "MATCH",
            "entity_match": True,
            "material_event_match": True,
            "temporal_match": True,
            "reason_code": "REQUIREMENT_SATISFIED"
        }
        self.adjudication_model_output = {
            "verdict": "DISMISS_CHALLENGE",
            "reason_code": "CHALLENGE_DISMISSED",
            "explanation": "Filing satisfies all required conditions"
        }
        self.web = types.SimpleNamespace(get=self.get)

    def get(self, url, headers=None):
        for pattern, res in self.responses.items():
            if pattern in url:
                return res
        return WebResponse(404, b"NOT_FOUND")

    def exec_prompt(self, prompt, *args, **kwargs):
        if "appellate" in str(prompt).lower():
            return self.adjudication_model_output
        return self.default_model_output

class MockEqPrinciple:
    def __init__(self):
        self.forced_output = None

    def prompt_comparative(self, fn, *args, **kwargs):
        if self.forced_output is not None:
            return self.forced_output
        return fn()

@pytest.fixture
def runtime(monkeypatch):
    nondet = MockNondet()
    eq_principle = MockEqPrinciple()
    transfers = []

    gl = types.ModuleType("genlayer")
    gl.__all__ = ["gl", "u256", "TreeMap", "Address"]
    gl.gl = gl
    gl.Contract = ContractBase
    gl.public = Public()
    gl.vm = types.SimpleNamespace(UserError=RuntimeError)
    gl.nondet = nondet
    gl.eq_principle = eq_principle
    gl.message = types.SimpleNamespace(sender_address=SPONSOR, value=0)
    gl.message_raw = {"datetime": "2026-09-26T00:00:00+00:00"}

    gl.get_contract_at = lambda addr: types.SimpleNamespace(
        emit_transfer=lambda value: transfers.append((str(addr).lower(), int(value)))
    )

    def contract_interface(_cls):
        class Proxy:
            def __init__(self, address):
                self.address = address
            def emit_transfer(self, value):
                return gl.get_contract_at(self.address).emit_transfer(value=value)
        return Proxy

    gl.evm = types.SimpleNamespace(contract_interface=contract_interface)
    gl.u256 = U256
    gl.TreeMap = TreeMap
    gl.Address = lambda val: val

    monkeypatch.setitem(sys.modules, "genlayer", gl)

    spec = importlib.util.spec_from_file_location(
        "draco_latch_test",
        Path("contracts/draco_latch.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.DracoLatch(), gl, nondet, eq_principle, transfers, module

# Helper functions
def set_sender(gl, address: str, value_wei: int = 0):
    gl.message.sender_address = address
    gl.message.value = value_wei

def create_sample_bounty(contract, gl, value_wei: int = 10**18):
    set_sender(gl, SPONSOR, value_wei)
    return contract.create_bounty(
        "Apple Executive Succession",
        "Confirm a planned COO succession naming the successor and transition duties.",
        "0000320193",
        "8-K",
        1700000000,
        1800000000,
        86400,
        300
    )

def setup_mock_sec_archive(nondet, doc_body: bytes = b"<html>Official SEC Filing Document Excerpt</html>"):
    nondet.responses = {
        "index-headers.html": WebResponse(200, "0000320193 0001140361-25-025275 ef20051741_8k.htm 8-K"),
        "ef20051741_8k.htm": WebResponse(200, doc_body)
    }

# ==============================================================================
# Unit & Adversarial Tests
# ==============================================================================

def test_permissionless_sponsor_and_self_claim_guard(runtime):
    contract, gl, _, _, _, _ = runtime
    set_sender(gl, SPONSOR, 10**18)
    bid = contract.create_bounty("Title Test", "x" * 50, "0000320193", "8-K", 100, 200, 3600, 300)
    assert int(bid) == 1
    assert contract.get_bounty(U256(1))["sponsor"] == SPONSOR

    # Sponsor cannot claim own bounty
    res = contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", "0" * 64)
    assert res == "ERR_SPONSOR_CANNOT_CLAIM"

def test_commit_reveal_claim_flow_and_anti_frontrunning(runtime):
    contract, gl, _, _, _, _ = runtime
    create_sample_bounty(contract, gl)

    set_sender(gl, CLAIMANT)
    salt = "super_secret_salt_123"
    accession = "0001140361-25-025275"
    doc = "ef20051741_8k.htm"
    digest = "79d278b5c34a40ec5618d5286c983120346ebb58ccd8587339533b88e7f22e37"

    # Compute commitment: sha256(claimant + accession + salt)
    commitment = hashlib.sha256(f"{CLAIMANT}:{accession}:{salt}".encode("utf-8")).hexdigest()

    # Phase 1: Hunter commits
    commit_res = contract.commit_claim(U256(1), commitment)
    assert commit_res == "COMMITMENT_RECORDED"

    # Frontrunner tries to reveal without commitment
    set_sender(gl, OUTSIDER)
    frontrun_res = contract.reveal_and_submit(U256(1), accession, doc, digest, salt)
    assert frontrun_res == "ERR_NO_ACTIVE_COMMITMENT"

    # True hunter reveals
    set_sender(gl, CLAIMANT)
    reveal_res = contract.reveal_and_submit(U256(1), accession, doc, digest, salt)
    assert int(reveal_res) == 1

    submission = contract.get_submission(U256(1))
    assert submission["status"] == "CLAIMED"
    assert submission["claimant"] == CLAIMANT

def test_commit_reveal_expiry_and_salt_mismatch(runtime):
    contract, gl, _, _, _, _ = runtime
    create_sample_bounty(contract, gl)

    set_sender(gl, CLAIMANT)
    salt = "my_salt"
    accession = "0001140361-25-025275"
    doc = "ef20051741_8k.htm"
    digest = "79d278b5c34a40ec5618d5286c983120346ebb58ccd8587339533b88e7f22e37"
    commitment = hashlib.sha256(f"{CLAIMANT}:{accession}:{salt}".encode("utf-8")).hexdigest()

    contract.commit_claim(U256(1), commitment)

    # Wrong salt
    bad_reveal = contract.reveal_and_submit(U256(1), accession, doc, digest, "wrong_salt")
    assert bad_reveal == "ERR_COMMITMENT_MISMATCH"

    # Commitment expiration (> 3600s)
    gl.message_raw["datetime"] = "2026-09-26T02:00:00+00:00"
    expired_reveal = contract.reveal_and_submit(U256(1), accession, doc, digest, salt)
    assert expired_reveal == "ERR_COMMITMENT_EXPIRED"

def test_happy_path_real_custody_and_payout(runtime):
    contract, gl, nondet, _, transfers, _ = runtime
    create_sample_bounty(contract, gl, 10**18)

    doc_content = b"<p>Apple Inc. announces COO succession transition details.</p>"
    doc_digest = hashlib.sha256(doc_content).hexdigest()
    setup_mock_sec_archive(nondet, doc_content)

    set_sender(gl, CLAIMANT)
    sid = contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", doc_digest)
    assert int(sid) == 1

    # Assessment
    set_sender(gl, SPONSOR)
    status = contract.assess_submission(U256(1), U256(1))
    assert status == "MATCH_PENDING"

    # Finalize before challenge deadline should fail
    set_sender(gl, CLAIMANT)
    assert contract.finalize_match(U256(1)) == "ERR_NOT_READY_FOR_FINALIZATION"

    # Advance time beyond challenge window
    gl.message_raw["datetime"] = "2026-09-26T00:10:00+00:00"
    finalize_res = contract.finalize_match(U256(1))
    assert finalize_res == "PAID"

    # Check that transfer was emitted to claimant
    assert transfers[-1] == (CLAIMANT, 10**18)

    # Verify totals
    totals = contract.get_totals()
    assert totals["locked_wei"] == "0"
    assert totals["paid_wei"] == str(10**18)

    # Replay finalization should fail
    assert contract.finalize_match(U256(1)) == "ERR_NOT_READY_FOR_FINALIZATION"

def test_active_dispute_challenge_mechanism(runtime):
    contract, gl, nondet, _, _, _ = runtime
    create_sample_bounty(contract, gl, 10**18)

    doc_content = b"Official SEC filing"
    setup_mock_sec_archive(nondet, doc_content)

    set_sender(gl, CLAIMANT)
    contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", hashlib.sha256(doc_content).hexdigest())

    set_sender(gl, SPONSOR)
    contract.assess_submission(U256(1), U256(1))

    # Sponsor challenges the match during the open window
    challenge_res = contract.challenge_match(U256(1), "Filing does not mention transition duties")
    assert challenge_res == "DISPUTED"

    submission = contract.get_submission(U256(1))
    assert submission["status"] == "DISPUTED"

    # Finalize attempt during dispute fails
    set_sender(gl, CLAIMANT)
    gl.message_raw["datetime"] = "2026-09-26T00:10:00+00:00"
    assert contract.finalize_match(U256(1)) == "ERR_NOT_READY_FOR_FINALIZATION"

def test_digest_mismatch_retries_and_sponsor_recovery(runtime):
    contract, gl, nondet, _, transfers, _ = runtime
    create_sample_bounty(contract, gl, 10**18)

    setup_mock_sec_archive(nondet, b"actual content")

    set_sender(gl, CLAIMANT)
    # Submit incorrect expected digest
    contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", "0" * 64)

    set_sender(gl, SPONSOR)
    assert contract.assess_submission(U256(1), U256(1)) == "UNRESOLVED"
    assert contract.get_submission(U256(1))["reason"] == "DIGEST_MISMATCH"

    # Retry 1
    assert contract.retry_unresolved(U256(1), U256(2)) == "CLAIMED"
    assert contract.assess_submission(U256(1), U256(3)) == "UNRESOLVED"

    # Retry 2 exceeds limit
    assert contract.retry_unresolved(U256(1), U256(4)) == "ERR_RETRY_LIMIT_EXHAUSTED"

    # Sponsor recovery is now authorized
    set_sender(gl, SPONSOR)
    recover_res = contract.recover_bounty(U256(1))
    assert recover_res == "REFUNDED"
    assert transfers[-1] == (SPONSOR, 10**18)

def test_semantic_not_match_reopens_bounty_and_blocks_accession_replay(runtime):
    contract, gl, nondet, _, _, _ = runtime
    create_sample_bounty(contract, gl, 10**18)

    doc_content = b"Unrelated filing"
    setup_mock_sec_archive(nondet, doc_content)

    # Set mock LLM output to NOT_MATCH
    nondet.default_model_output = {
        "verdict": "NOT_MATCH",
        "entity_match": True,
        "material_event_match": False,
        "temporal_match": True,
        "reason_code": "EVENT_MISMATCH"
    }

    set_sender(gl, CLAIMANT)
    contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", hashlib.sha256(doc_content).hexdigest())

    set_sender(gl, SPONSOR)
    assert contract.assess_submission(U256(1), U256(1)) == "NOT_MATCH"

    # Bounty cleanly reopens
    bounty = contract.get_bounty(U256(1))
    assert bounty["status"] == "OPEN"
    assert bounty["active_submission"] == 0

    # Accession replay is blocked
    set_sender(gl, CLAIMANT)
    replay_res = contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", hashlib.sha256(doc_content).hexdigest())
    assert replay_res == "ERR_ACCESSION_ALREADY_USED"

def test_metadata_provenance_failure_fails_closed(runtime):
    contract, gl, nondet, _, _, _ = runtime
    create_sample_bounty(contract, gl, 10**18)

    doc_content = b"Valid document"
    # Provide wrong index headers (missing accession / CIK)
    nondet.responses = {
        "index-headers.html": WebResponse(200, "Wrong corporate header metadata"),
        "ef20051741_8k.htm": WebResponse(200, doc_content)
    }

    set_sender(gl, CLAIMANT)
    contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", hashlib.sha256(doc_content).hexdigest())

    set_sender(gl, SPONSOR)
    assert contract.assess_submission(U256(1), U256(1)) == "UNRESOLVED"
    assert contract.get_submission(U256(1))["reason"] == "PROVENANCE_MISMATCH"

def test_model_contradiction_fails_closed(runtime):
    contract, gl, nondet, _, _, _ = runtime
    create_sample_bounty(contract, gl, 10**18)

    doc_content = b"Valid document"
    setup_mock_sec_archive(nondet, doc_content)

    # Inconsistent model: verdict is MATCH but temporal_match is False
    nondet.default_model_output = {
        "verdict": "MATCH",
        "entity_match": True,
        "material_event_match": True,
        "temporal_match": False,
        "reason_code": "REQUIREMENT_SATISFIED"
    }

    set_sender(gl, CLAIMANT)
    contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", hashlib.sha256(doc_content).hexdigest())

    set_sender(gl, SPONSOR)
    assert contract.assess_submission(U256(1), U256(1)) == "UNRESOLVED"
    assert contract.get_submission(U256(1))["reason"] == "MODEL_CONTRADICTION"

def test_consensus_divergence_fails_closed(runtime):
    contract, gl, nondet, eq_principle, _, _ = runtime
    create_sample_bounty(contract, gl, 10**18)

    doc_content = b"Valid document"
    setup_mock_sec_archive(nondet, doc_content)

    # Force conflicting consensus text
    eq_principle.forced_output = json.dumps({"error": "validators diverged"})

    set_sender(gl, CLAIMANT)
    contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", hashlib.sha256(doc_content).hexdigest())

    set_sender(gl, SPONSOR)
    assert contract.assess_submission(U256(1), U256(1)) == "UNRESOLVED"

def test_outsider_cannot_grief_assessment_or_retry_budget(runtime):
    contract, gl, nondet, _, _, _ = runtime
    create_sample_bounty(contract, gl, 10**18)
    setup_mock_sec_archive(nondet)

    set_sender(gl, CLAIMANT)
    contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", "0" * 64)

    # Outsider attempts to assess
    set_sender(gl, OUTSIDER)
    assert contract.assess_submission(U256(1), U256(1)) == "ERR_ONLY_PARTICIPANT_PERMITTED"
    assert contract.get_submission(U256(1))["attempts"] == 0

def test_invalid_payable_inputs_are_immediately_refunded(runtime):
    contract, gl, _, _, transfers, _ = runtime
    set_sender(gl, SPONSOR, 10**18)

    # Invalid title (<5 chars)
    res = contract.create_bounty("x", "x" * 50, "0000320193", "8-K", 100, 200, 3600, 300)
    assert res == "ERR_INVALID_TEXT_BOUNDS"
    assert transfers[-1] == (SPONSOR, 10**18)
    assert contract.get_totals()["locked_wei"] == "0"

def test_economic_conservation_across_independent_bounties(runtime):
    contract, gl, _, _, transfers, _ = runtime

    # Bounty 1: 2 GEN
    set_sender(gl, SPONSOR, 2 * 10**18)
    bid1 = contract.create_bounty("Bounty 1", "x" * 50, "0000320193", "8-K", 100, 200, 3600, 300)

    # Bounty 2: 3 GEN
    set_sender(gl, OUTSIDER, 3 * 10**18)
    bid2 = contract.create_bounty("Bounty 2", "y" * 50, "0000320193", "8-K", 100, 200, 3600, 300)

    assert contract.get_totals()["locked_wei"] == str(5 * 10**18)

    # Expire submission deadline
    gl.message_raw["datetime"] = "2026-09-28T00:00:00+00:00"

    set_sender(gl, SPONSOR)
    assert contract.recover_bounty(U256(1)) == "REFUNDED"

    set_sender(gl, OUTSIDER)
    assert contract.recover_bounty(U256(2)) == "REFUNDED"

    totals = contract.get_totals()
    assert totals["locked_wei"] == "0"
    assert totals["refunded_wei"] == str(5 * 10**18)
    assert transfers[-2:] == [(SPONSOR, 2 * 10**18), (OUTSIDER, 3 * 10**18)]

def test_html_tag_stripping_and_sanitization(runtime):
    _, _, _, _, _, module = runtime
    raw_html = (
        "<html><head><script>alert('xss');</script><style>.hidden{display:none;}</style></head>"
        "<body><h1>Item 5.02 Departure of Directors</h1>"
        "<p>On June 25, 2025, Apple Inc. announced a planned COO transition.</p>"
        "</body></html>"
    )
    cleaned = module.strip_html_tags(raw_html)
    assert "<script>" not in cleaned
    assert "alert" not in cleaned
    assert "<style>" not in cleaned
    assert "<h1>" not in cleaned
    assert "Item 5.02 Departure of Directors On June 25, 2025, Apple Inc. announced a planned COO transition." in cleaned

def test_active_commit_reserves_slot_against_direct_submission(runtime):
    """
    Verifies that an active commitment transitions the bounty to RESERVED and
    strictly blocks direct submissions and racing committers until revealed or expired.
    """
    contract, gl, _, _, _, _ = runtime
    create_sample_bounty(contract, gl)

    set_sender(gl, CLAIMANT)
    salt = "secret_salt"
    accession = "0001140361-25-025275"
    doc = "ef20051741_8k.htm"
    digest = "79d278b5c34a40ec5618d5286c983120346ebb58ccd8587339533b88e7f22e37"
    commitment = hashlib.sha256(f"{CLAIMANT}:{accession}:{salt}".encode("utf-8")).hexdigest()

    # Hunter A commits
    assert contract.commit_claim(U256(1), commitment) == "COMMITMENT_RECORDED"
    bounty = contract.get_bounty(U256(1))
    assert bounty["status"] == "RESERVED"
    assert bounty["active_committer"] == CLAIMANT

    # Outsider tries direct submission while reservation is active -> BLOCKED
    set_sender(gl, OUTSIDER)
    blocked_direct = contract.submit_direct(U256(1), accession, doc, digest)
    assert blocked_direct == "ERR_SLOT_RESERVED_BY_COMMITMENT"

    # Outsider tries to commit while reservation is active -> BLOCKED
    outsider_commit = hashlib.sha256(f"{OUTSIDER}:{accession}:salt2".encode("utf-8")).hexdigest()
    blocked_commit = contract.commit_claim(U256(1), outsider_commit)
    assert blocked_commit == "ERR_BOUNTY_ALREADY_RESERVED"

    # True committer successfully reveals and claims slot
    set_sender(gl, CLAIMANT)
    reveal_res = contract.reveal_and_submit(U256(1), accession, doc, digest, salt)
    assert int(reveal_res) == 1

    bounty_after = contract.get_bounty(U256(1))
    assert bounty_after["status"] == "CLAIMED"
    assert bounty_after["active_committer"] == ""

def test_expired_commit_releases_slot_for_direct_submission(runtime):
    """
    Verifies that when a commitment reservation expires without reveal,
    the reservation lock lifts and direct submission is permitted.
    """
    contract, gl, _, _, _, _ = runtime
    create_sample_bounty(contract, gl)

    set_sender(gl, CLAIMANT)
    salt = "secret_salt"
    accession = "0001140361-25-025275"
    doc = "ef20051741_8k.htm"
    digest = "79d278b5c34a40ec5618d5286c983120346ebb58ccd8587339533b88e7f22e37"
    commitment = hashlib.sha256(f"{CLAIMANT}:{accession}:{salt}".encode("utf-8")).hexdigest()

    contract.commit_claim(U256(1), commitment)
    assert contract.get_bounty(U256(1))["status"] == "RESERVED"

    # Advance time beyond commitment expiry (1 hour = 3600s)
    gl.message_raw["datetime"] = "2026-09-26T01:05:00+00:00"

    # Outsider submits directly after expiry -> SUCCEEDS
    set_sender(gl, OUTSIDER)
    sid = contract.submit_direct(U256(1), accession, doc, digest)
    assert int(sid) == 1

    sub = contract.get_submission(U256(1))
    assert sub["status"] == "CLAIMED"
    assert sub["claimant"] == OUTSIDER

def test_dispute_adjudication_dismisses_challenge_and_settles_hunter_payout(runtime):
    """
    Full Adjudication & Settlement Path 1 (Hunter Payout):
    1. Submission provisionally approved as MATCH_PENDING.
    2. Sponsor challenges match -> status DISPUTED.
    3. Validators adjudicate dispute and find challenge groundless (DISMISS_CHALLENGE).
    4. Submission transitions to MATCH_UPHELD.
    5. Claimant finalizes match -> receives 100% principal payout.
    """
    contract, gl, nondet, _, transfers, _ = runtime
    create_sample_bounty(contract, gl, 10**18)

    doc_content = b"Official SEC filing with complete executive transition disclosures"
    setup_mock_sec_archive(nondet, doc_content)

    set_sender(gl, CLAIMANT)
    contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", hashlib.sha256(doc_content).hexdigest())

    set_sender(gl, SPONSOR)
    contract.assess_submission(U256(1), U256(1))
    assert contract.get_submission(U256(1))["status"] == "MATCH_PENDING"

    # Sponsor challenges
    challenge_res = contract.challenge_match(U256(1), "Alleging duties missing from filing")
    assert challenge_res == "DISPUTED"
    assert contract.get_bounty(U256(1))["status"] == "DISPUTED"

    # Configure appellate validator model output: Dismiss challenge (Hunter wins)
    nondet.adjudication_model_output = {
        "verdict": "DISMISS_CHALLENGE",
        "reason_code": "CHALLENGE_DISMISSED",
        "explanation": "Filing substantively satisfies all required conditions"
    }

    # Hunter (or Sponsor) triggers adjudication
    set_sender(gl, CLAIMANT)
    curr_rev = contract.get_submission(U256(1))["revision"]
    adj_status = contract.adjudicate_dispute(U256(1), U256(curr_rev))
    assert adj_status == "MATCH_UPHELD"
    assert contract.get_submission(U256(1))["status"] == "MATCH_UPHELD"
    assert contract.get_bounty(U256(1))["status"] == "MATCH_UPHELD"

    # Hunter finalizes match and receives payout
    finalize_res = contract.finalize_match(U256(1))
    assert finalize_res == "PAID"
    assert contract.get_submission(U256(1))["status"] == "PAID"
    assert contract.get_bounty(U256(1))["status"] == "PAID"

    # Principal transferred to Hunter
    assert transfers[-1] == (CLAIMANT, 10**18)
    totals = contract.get_totals()
    assert totals["locked_wei"] == "0"
    assert totals["paid_wei"] == str(10**18)

def test_dispute_adjudication_upholds_challenge_and_authorizes_sponsor_recovery(runtime):
    """
    Full Adjudication & Settlement Path 2 (Sponsor Recovery):
    1. Submission provisionally approved as MATCH_PENDING.
    2. Sponsor challenges match -> status DISPUTED.
    3. Validators adjudicate dispute and uphold challenge (UPHOLD_CHALLENGE).
    4. Submission and bounty transition to CHALLENGE_UPHELD.
    5. Hunter finalization rejected.
    6. Sponsor calls recover_bounty -> receives 100% refund.
    """
    contract, gl, nondet, _, transfers, _ = runtime
    create_sample_bounty(contract, gl, 10**18)

    doc_content = b"Official SEC filing"
    setup_mock_sec_archive(nondet, doc_content)

    set_sender(gl, CLAIMANT)
    contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", hashlib.sha256(doc_content).hexdigest())

    set_sender(gl, SPONSOR)
    contract.assess_submission(U256(1), U256(1))

    # Sponsor challenges
    contract.challenge_match(U256(1), "Filing does not name executive transition duties")

    # Configure appellate validator model output: Uphold challenge (Sponsor wins)
    nondet.adjudication_model_output = {
        "verdict": "UPHOLD_CHALLENGE",
        "reason_code": "CHALLENGE_UPHELD",
        "explanation": "Filing is missing required material transition duties"
    }

    # Sponsor triggers adjudication
    curr_rev = contract.get_submission(U256(1))["revision"]
    adj_status = contract.adjudicate_dispute(U256(1), U256(curr_rev))
    assert adj_status == "CHALLENGE_UPHELD"
    assert contract.get_bounty(U256(1))["status"] == "CHALLENGE_UPHELD"

    # Hunter cannot finalize
    set_sender(gl, CLAIMANT)
    assert contract.finalize_match(U256(1)) == "ERR_NOT_READY_FOR_FINALIZATION"

    # Sponsor recovers principal
    set_sender(gl, SPONSOR)
    recover_res = contract.recover_bounty(U256(1))
    assert recover_res == "REFUNDED"
    assert contract.get_bounty(U256(1))["status"] == "REFUNDED"

    # Refund transferred to Sponsor
    assert transfers[-1] == (SPONSOR, 10**18)
    totals = contract.get_totals()
    assert totals["locked_wei"] == "0"
    assert totals["refunded_wei"] == str(10**18)

def test_dispute_sponsor_withdraw_challenge_and_hunter_payout(runtime):
    """
    Verifies that the Sponsor can voluntarily withdraw a challenge,
    unlocking immediate finalization for the hunter.
    """
    contract, gl, nondet, _, transfers, _ = runtime
    create_sample_bounty(contract, gl, 10**18)

    doc_content = b"Official SEC filing"
    setup_mock_sec_archive(nondet, doc_content)

    set_sender(gl, CLAIMANT)
    contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", hashlib.sha256(doc_content).hexdigest())

    set_sender(gl, SPONSOR)
    contract.assess_submission(U256(1), U256(1))
    contract.challenge_match(U256(1), "Temporary concern")
    assert contract.get_bounty(U256(1))["status"] == "DISPUTED"

    # Sponsor voluntarily withdraws challenge
    withdraw_res = contract.withdraw_challenge(U256(1))
    assert withdraw_res == "MATCH_UPHELD"

    # Claimant finalizes payout
    set_sender(gl, CLAIMANT)
    assert contract.finalize_match(U256(1)) == "PAID"
    assert transfers[-1] == (CLAIMANT, 10**18)

def test_dispute_timeout_abandonment_settles_hunter(runtime):
    """
    Anti-Deadlock Invariant:
    If a sponsor files a challenge and abandons it without adjudication,
    the dispute window expires and the hunter can finalize payout.
    Prevents unilateral indefinite lockup.
    """
    contract, gl, nondet, _, transfers, _ = runtime
    create_sample_bounty(contract, gl, 10**18)

    doc_content = b"Official SEC filing"
    setup_mock_sec_archive(nondet, doc_content)

    set_sender(gl, CLAIMANT)
    contract.submit_direct(U256(1), "0001140361-25-025275", "ef20051741_8k.htm", hashlib.sha256(doc_content).hexdigest())

    set_sender(gl, SPONSOR)
    contract.assess_submission(U256(1), U256(1))
    contract.challenge_match(U256(1), "Abandoned challenge")

    # Time advances beyond dispute deadline (e.g. 2 days later)
    gl.message_raw["datetime"] = "2026-09-28T01:00:00+00:00"

    # Hunter finalizes after dispute deadline lapsed
    set_sender(gl, CLAIMANT)
    assert contract.finalize_match(U256(1)) == "PAID"
    assert transfers[-1] == (CLAIMANT, 10**18)

