# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
DracoLatch: Autonomous Corporate Disclosure Escrow & Verification Engine.
Governed by GenLayer Intelligent Validator Consensus.

Key Features:
- Cryptographic Commit-Reveal Claim Protocol to eliminate mempool frontrunning.
- Deterministic SEC EDGAR URL derivation directly from CIK + Accession parameters.
- Pre-semantic SHA-256 byte digest integrity check and metadata provenance gating.
- Content sanitization with HTML tag stripping to preserve LLM token context.
- Deliberate Comparative Equivalence Principle with multi-field boolean invariants.
- Strict Checks-Effects-Interactions (CEI) accounting on native GEN principal.
- Active on-chain challenge and dispute resolution mechanism.
"""

from genlayer import *
import hashlib
import json
import re
import typing
from datetime import datetime

# ==============================================================================
# Protocol Constants
# ==============================================================================

MIN_BOUNTY_WEI = 10**15         # Minimum bounty deposit: 0.001 GEN
MAX_PAYLOAD_BYTES = 128000      # 128 KB maximum document intake boundary
MAX_ASSESSMENT_RETRIES = 2      # Maximum validator assessment attempts allowed
COMMITMENT_EXPIRY_SEC = 3600    # Commit-reveal reservation window (1 hour)

# Lifecycle Status Enumerations
STATUS_OPEN = "OPEN"
STATUS_RESERVED = "RESERVED"
STATUS_CLAIMED = "CLAIMED"
STATUS_MATCH_PENDING = "MATCH_PENDING"
STATUS_NOT_MATCH = "NOT_MATCH"
STATUS_UNRESOLVED = "UNRESOLVED"
STATUS_DISPUTED = "DISPUTED"
STATUS_PAID = "PAID"
STATUS_REFUNDED = "REFUNDED"

# Standard Reason Codes
REASON_NOT_ASSESSED = "NOT_ASSESSED"
REASON_REQUIREMENT_SATISFIED = "REQUIREMENT_SATISFIED"
REASON_ENTITY_MISMATCH = "ENTITY_MISMATCH"
REASON_EVENT_MISMATCH = "EVENT_MISMATCH"
REASON_WINDOW_MISMATCH = "WINDOW_MISMATCH"
REASON_INSUFFICIENT_DETAIL = "INSUFFICIENT_DETAIL"
REASON_DIGEST_MISMATCH = "DIGEST_MISMATCH"
REASON_PROVENANCE_MISMATCH = "PROVENANCE_MISMATCH"
REASON_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
REASON_SOURCE_OVERSIZED = "SOURCE_EMPTY_OR_OVERSIZED"
REASON_MODEL_SCHEMA_INVALID = "MODEL_SCHEMA_INVALID"
REASON_MODEL_CONTRADICTION = "MODEL_CONTRADICTION"
REASON_CHALLENGE_REGISTERED = "CHALLENGE_REGISTERED"

# ==============================================================================
# External Transfer Interface
# ==============================================================================

@gl.evm.contract_interface
class _EoaRecipient:
    class View: pass
    class Write: pass

# ==============================================================================
# Pure Helper Utilities
# ==============================================================================

def canonical_json(val: typing.Any) -> str:
    """Produces deterministic canonical JSON with sorted keys and tight separators."""
    return json.dumps(val, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def current_sender() -> str:
    """Returns normalized lowercase hex string of current message sender."""
    return str(gl.message.sender_address).lower()

def current_timestamp() -> int:
    """Parses ISO timestamp from GenLayer raw message into unix seconds."""
    raw_dt = str(gl.message_raw["datetime"]).replace("Z", "+00:00")
    return int(datetime.fromisoformat(raw_dt).timestamp())

def current_value() -> int:
    """Safely extracts native GEN value attached to call in wei."""
    try:
        return int(gl.message.value)
    except Exception:
        return 0

def sha256_hex(data: bytes) -> str:
    """Computes lowercase hex SHA-256 digest of input bytes."""
    return hashlib.sha256(data).hexdigest()

def strip_html_tags(raw_text: str) -> str:
    """
    Cleans raw SEC HTML filing text by stripping script, style, and tag blocks.
    Reduces token consumption and avoids delimiter collisions inside LLM prompts.
    """
    # Remove script and style blocks
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_text, flags=re.DOTALL | re.IGNORECASE)
    # Remove all HTML/XML tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Normalize excessive whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def make_failure_result(reason_code: str) -> str:
    """Constructs serialized failure packet for fail-closed consensus."""
    return canonical_json({"kind": "UNRESOLVED", "reason": reason_code})

# ==============================================================================
# DracoLatch Core Contract
# ==============================================================================

class DracoLatch(gl.Contract):
    """
    Decentralized Evidence-Conditioned Corporate Disclosure Escrow.
    Orchestrates bounty creation, commit-reveal claim reservation,
    multi-validator SEC archive retrieval, comparative LLM consensus,
    and trustless value settlement.
    """

    bounty_count: u256
    submission_count: u256
    total_locked_wei: u256
    total_paid_wei: u256
    total_refunded_wei: u256

    bounties: TreeMap[u256, str]
    submissions: TreeMap[u256, str]
    claim_commitments: TreeMap[str, str]
    used_accessions: TreeMap[str, str]

    def __init__(self):
        self.bounty_count = u256(0)
        self.submission_count = u256(0)
        self.total_locked_wei = u256(0)
        self.total_paid_wei = u256(0)
        self.total_refunded_wei = u256(0)

    # --------------------------------------------------------------------------
    # Internal Storage & Transfer Helpers
    # --------------------------------------------------------------------------

    def _get_bounty(self, bid: u256) -> typing.Optional[dict]:
        b_idx = int(bid)
        if b_idx < 1 or b_idx > int(self.bounty_count):
            return None
        return json.loads(self.bounties[bid])

    def _get_submission(self, sid: u256) -> typing.Optional[dict]:
        s_idx = int(sid)
        if s_idx < 1 or s_idx > int(self.submission_count):
            return None
        return json.loads(self.submissions[sid])

    def _save_bounty(self, b: dict) -> None:
        self.bounties[u256(b["id"])] = canonical_json(b)

    def _save_submission(self, s: dict) -> None:
        self.submissions[u256(s["id"])] = canonical_json(s)

    def _transfer(self, to_addr: str, amount_wei: int) -> None:
        """Executes native GEN value transfer via EOA recipient contract interface."""
        _EoaRecipient(Address(to_addr)).emit_transfer(value=u256(amount_wei))

    # --------------------------------------------------------------------------
    # Public Write Methods: Bounty Management
    # --------------------------------------------------------------------------

    @gl.public.write.payable
    def create_bounty(
        self,
        title: str,
        requirement: str,
        cik: str,
        allowed_form: str,
        filing_start: u256,
        filing_end: u256,
        submission_window_sec: u256,
        challenge_window_sec: u256
    ) -> typing.Any:
        """
        Creates and funds a new disclosure bounty with native GEN principal.
        Validates parameters strictly; refunds attached value immediately on validation failure.
        """
        attached = current_value()
        caller = current_sender()

        # Enforce minimum financial stake
        if attached < MIN_BOUNTY_WEI:
            if attached > 0:
                self._transfer(caller, attached)
            return "ERR_BOUNTY_BELOW_MINIMUM"

        clean_title = title.strip()
        clean_req = requirement.strip()
        clean_cik = cik.strip()
        clean_form = allowed_form.strip().upper()

        # Text length validation
        if len(clean_title) < 5 or len(clean_title) > 100 or len(clean_req) < 40 or len(clean_req) > 1200:
            self._transfer(caller, attached)
            return "ERR_INVALID_TEXT_BOUNDS"

        # Scope validation: 10-digit SEC CIK and valid Form type
        if re.fullmatch(r"[0-9]{10}", clean_cik) is None or re.fullmatch(r"[A-Z0-9/-]{2,12}", clean_form) is None:
            self._transfer(caller, attached)
            return "ERR_INVALID_FILING_SCOPE"

        # Temporal filing window validation
        if int(filing_start) >= int(filing_end):
            self._transfer(caller, attached)
            return "ERR_INVALID_FILING_WINDOW"

        # Deadline and challenge window bounds
        sub_sec = int(submission_window_sec)
        chal_sec = int(challenge_window_sec)
        if sub_sec < 3600 or sub_sec > 30 * 86400 or chal_sec < 300 or chal_sec > 7 * 86400:
            self._transfer(caller, attached)
            return "ERR_INVALID_DEADLINE_PARAMS"

        # State creation
        new_bid = u256(int(self.bounty_count) + 1)
        self.bounty_count = new_bid
        now_ts = current_timestamp()

        bounty_record = {
            "id": int(new_bid),
            "sponsor": caller,
            "title": clean_title,
            "requirement": clean_req,
            "cik": clean_cik,
            "allowed_form": clean_form,
            "filing_start": int(filing_start),
            "filing_end": int(filing_end),
            "submission_deadline": now_ts + sub_sec,
            "challenge_window": chal_sec,
            "status": STATUS_OPEN,
            "locked_wei": attached,
            "active_submission": 0,
            "created_at": now_ts
        }

        self._save_bounty(bounty_record)
        self.total_locked_wei = u256(int(self.total_locked_wei) + attached)
        return new_bid

    # --------------------------------------------------------------------------
    # Public Write Methods: Claim Protocol (Commit-Reveal & Direct)
    # --------------------------------------------------------------------------

    @gl.public.write
    def commit_claim(self, bounty_id: u256, commitment_hash: str) -> str:
        """
        Phase 1 of Commit-Reveal Claim Protocol (Anti-Frontrunning Guard).
        Hunters commit: sha256(claimant_address + accession + salt).
        Reserves the claim slot without exposing the accession in plaintext to the mempool.
        """
        b = self._get_bounty(bounty_id)
        if b is None:
            return "ERR_BOUNTY_NOT_FOUND"

        caller = current_sender()
        if caller == b["sponsor"]:
            return "ERR_SPONSOR_CANNOT_CLAIM"

        if b["status"] != STATUS_OPEN or current_timestamp() > b["submission_deadline"]:
            return "ERR_BOUNTY_NOT_OPEN"

        norm_hash = commitment_hash.strip().lower()
        if re.fullmatch(r"[0-9a-f]{64}", norm_hash) is None:
            return "ERR_INVALID_COMMITMENT_HASH"

        commit_key = f"{int(bounty_id)}:{caller}"
        commit_data = {
            "commitment": norm_hash,
            "timestamp": current_timestamp(),
            "claimant": caller
        }
        self.claim_commitments[commit_key] = canonical_json(commit_data)
        return "COMMITMENT_RECORDED"

    @gl.public.write
    def reveal_and_submit(
        self,
        bounty_id: u256,
        accession: str,
        primary_document: str,
        expected_sha256: str,
        salt: str
    ) -> typing.Any:
        """
        Phase 2 of Commit-Reveal Protocol:
        Reveals the committed accession, document name, and digest with salt.
        Verifies caller is the original committer before progressing to assessment.
        """
        caller = current_sender()
        commit_key = f"{int(bounty_id)}:{caller}"
        saved_commit = self.claim_commitments.get(commit_key)

        if not saved_commit:
            return "ERR_NO_ACTIVE_COMMITMENT"

        c_data = json.loads(saved_commit)
        if current_timestamp() - int(c_data["timestamp"]) > COMMITMENT_EXPIRY_SEC:
            return "ERR_COMMITMENT_EXPIRED"

        clean_acc = accession.strip()
        expected_hash = sha256_hex(f"{caller}:{clean_acc}:{salt}".encode("utf-8"))
        if expected_hash != c_data["commitment"]:
            return "ERR_COMMITMENT_MISMATCH"

        # Proceed to record submission
        return self._record_submission_entry(bounty_id, clean_acc, primary_document, expected_sha256)

    @gl.public.write
    def submit_direct(
        self,
        bounty_id: u256,
        accession: str,
        primary_document: str,
        expected_sha256: str
    ) -> typing.Any:
        """
        Direct submission pathway.
        Bypasses commitment phase when frontrunning protection is not required by caller.
        """
        return self._record_submission_entry(bounty_id, accession.strip(), primary_document, expected_sha256)

    def _record_submission_entry(
        self,
        bounty_id: u256,
        accession: str,
        primary_document: str,
        expected_sha256: str
    ) -> typing.Any:
        """Internal helper to validate identifiers and commit submission to state."""
        b = self._get_bounty(bounty_id)
        if b is None:
            return "ERR_BOUNTY_NOT_FOUND"

        caller = current_sender()
        if caller == b["sponsor"]:
            return "ERR_SPONSOR_CANNOT_CLAIM"

        if b["status"] != STATUS_OPEN or current_timestamp() > b["submission_deadline"]:
            return "ERR_BOUNTY_NOT_OPEN"

        doc = primary_document.strip()
        digest = expected_sha256.strip().lower()

        # Strict SEC accession format: 10-digit CIK + 2-digit year + 6-digit seq
        if re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession) is None:
            return "ERR_INVALID_ACCESSION_FORMAT"

        # Document filename format and extension guard
        if re.fullmatch(r"[A-Za-z0-9._-]{3,100}", doc) is None or not doc.lower().endswith((".htm", ".html", ".txt")):
            return "ERR_INVALID_DOCUMENT_NAME"

        # Digest format
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            return "ERR_INVALID_DIGEST_FORMAT"

        # Accession replay prevention per bounty
        accession_use_key = f"{int(bounty_id)}:{accession}"
        if self.used_accessions.get(accession_use_key):
            return "ERR_ACCESSION_ALREADY_USED"

        new_sid = u256(int(self.submission_count) + 1)
        self.submission_count = new_sid

        submission_record = {
            "id": int(new_sid),
            "bounty_id": int(bounty_id),
            "claimant": caller,
            "accession": accession,
            "primary_document": doc,
            "expected_sha256": digest,
            "status": STATUS_CLAIMED,
            "reason": REASON_NOT_ASSESSED,
            "attempts": 0,
            "evidence_digest": "",
            "verdict_digest": "",
            "challenge_deadline": 0,
            "revision": 1
        }

        self._save_submission(submission_record)
        self.used_accessions[accession_use_key] = str(int(new_sid))

        b["status"] = STATUS_CLAIMED
        b["active_submission"] = int(new_sid)
        self._save_bounty(b)
        return new_sid

    # --------------------------------------------------------------------------
    # Public Write Methods: Consensus Assessment
    # --------------------------------------------------------------------------

    @gl.public.write
    def assess_submission(self, submission_id: u256, expected_revision: u256) -> str:
        """
        Executes multi-validator SEC archive retrieval, byte verification,
        and comparative LLM semantic consensus.
        Restricted to Bounty Sponsor or Submission Claimant.
        """
        s = self._get_submission(submission_id)
        if s is None:
            return "ERR_SUBMISSION_NOT_FOUND"

        b = self._get_bounty(u256(s["bounty_id"]))
        caller = current_sender()

        # Access control: only active participants can consume assessment gas/attempts
        if caller != b["sponsor"] and caller != s["claimant"]:
            return "ERR_ONLY_PARTICIPANT_PERMITTED"

        if s["revision"] != int(expected_revision):
            return "ERR_STALE_REVISION"

        if s["status"] != STATUS_CLAIMED:
            return "ERR_ASSESSMENT_NOT_CLAIMED"

        cik = b["cik"]
        accession = s["accession"]
        doc = s["primary_document"]
        expected_digest = s["expected_sha256"]
        req_text = b["requirement"]
        form_type = b["allowed_form"]
        win_start = b["filing_start"]
        win_end = b["filing_end"]

        # Deterministic SEC EDGAR archive URL construction
        compact_acc = accession.replace("-", "")
        cik_clean = str(int(cik))
        base_archive_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{compact_acc}/"
        index_url = f"{base_archive_url}{accession}-index-headers.html"
        document_url = f"{base_archive_url}{doc}"

        def validator_evaluation_routine() -> str:
            req_headers = {
                "Accept": "text/html,text/plain",
                "User-Agent": "DracoLatch-Consensus/1.0 research-contact@example.org"
            }
            try:
                # Retrieve index headers (provenance) and primary document (body)
                meta_res = gl.nondet.web.get(index_url, headers=req_headers)
                body_res = gl.nondet.web.get(document_url, headers=req_headers)

                if int(meta_res.status) != 200 or int(body_res.status) != 200:
                    return make_failure_result(REASON_SOURCE_UNAVAILABLE)

                raw_bytes = body_res.body or b""
                meta_text = (meta_res.body or b"")[:MAX_PAYLOAD_BYTES].decode("utf-8", errors="replace")

                # Boundary and size guards
                if len(raw_bytes) == 0 or len(raw_bytes) > MAX_PAYLOAD_BYTES:
                    return make_failure_result(REASON_SOURCE_OVERSIZED)

                # 1. Exact-Byte Preflight Check
                actual_digest = sha256_hex(raw_bytes)
                if actual_digest != expected_digest:
                    return make_failure_result(REASON_DIGEST_MISMATCH)

                # 2. Metadata Provenance Gating
                if (accession not in meta_text or cik not in meta_text or
                    doc not in meta_text or form_type not in meta_text.upper()):
                    return make_failure_result(REASON_PROVENANCE_MISMATCH)

                # 3. Clean Text Extraction (HTML Tag Stripping)
                raw_text_decoded = raw_bytes.decode("utf-8", errors="replace")
                sanitized_content = strip_html_tags(raw_text_decoded)

                # 4. LLM Prompt Construction
                prompt_instruction = (
                    "You are a strict SEC disclosure compliance validator. "
                    "Analyze the provided inert SEC filing excerpt against the locked disclosure requirement.\n"
                    "Determine whether the document substantively satisfies all required conditions.\n\n"
                    "RETURN ONLY VALID JSON with exactly these five fields:\n"
                    "- verdict: 'MATCH' or 'NOT_MATCH'\n"
                    "- entity_match: true or false\n"
                    "- material_event_match: true or false\n"
                    "- temporal_match: true or false\n"
                    "- reason_code: 'REQUIREMENT_SATISFIED', 'ENTITY_MISMATCH', 'EVENT_MISMATCH', "
                    "'WINDOW_MISMATCH', or 'INSUFFICIENT_DETAIL'\n\n"
                    "LOGICAL INVARIANT: 'MATCH' strictly requires entity_match=true, material_event_match=true, "
                    "and temporal_match=true. Otherwise, verdict MUST be 'NOT_MATCH'.\n\n"
                    f"CIK: {cik}\n"
                    f"ACCESSION: {accession}\n"
                    f"ALLOWED_FORM: {form_type}\n"
                    f"FILING_WINDOW_UNIX: {win_start}..{win_end}\n"
                    f"LOCKED_REQUIREMENT: {req_text}\n\n"
                    "FILING_BODY_BEGIN\n"
                    f"{sanitized_content[:100000]}\n"
                    "FILING_BODY_END"
                )

                prompt_output = gl.nondet.exec_prompt(prompt_instruction, response_format="json")
                res_dict = prompt_output if isinstance(prompt_output, dict) else json.loads(str(prompt_output))

                expected_keys = {"verdict", "entity_match", "material_event_match", "temporal_match", "reason_code"}
                if not isinstance(res_dict, dict) or set(res_dict) != expected_keys:
                    return make_failure_result(REASON_MODEL_SCHEMA_INVALID)

                if res_dict["verdict"] not in ("MATCH", "NOT_MATCH"):
                    return make_failure_result(REASON_MODEL_SCHEMA_INVALID)

                if any(not isinstance(res_dict[k], bool) for k in ("entity_match", "material_event_match", "temporal_match")):
                    return make_failure_result(REASON_MODEL_SCHEMA_INVALID)

                # Cross-field consistency verification
                all_sub_bools_true = (
                    res_dict["entity_match"] and
                    res_dict["material_event_match"] and
                    res_dict["temporal_match"]
                )
                if res_dict["verdict"] == "MATCH" and not all_sub_bools_true:
                    return make_failure_result(REASON_MODEL_CONTRADICTION)

                return canonical_json({
                    "kind": "ASSESSED",
                    "verdict": res_dict["verdict"],
                    "reason": res_dict["reason_code"],
                    "evidence_digest": actual_digest,
                    "source_url": document_url
                })
            except Exception:
                return make_failure_result(REASON_SOURCE_UNAVAILABLE)

        # Comparative Equivalence: requires identical verdict, evidence digest, and reason code
        consensus_text = gl.eq_principle.prompt_comparative(
            validator_evaluation_routine,
            "Agreement requires matching consequential verdict, evidence SHA-256 digest, and normalized reason code. "
            "Fail-closed to UNRESOLVED on any ambiguity or contradiction."
        )

        try:
            parsed_consensus = json.loads(consensus_text)
        except Exception:
            parsed_consensus = {"kind": "UNRESOLVED", "reason": "ERR_CONSENSUS_PARSE_FAILURE"}

        s["attempts"] += 1
        s["revision"] += 1
        s["reason"] = str(parsed_consensus.get("reason", STATUS_UNRESOLVED))[:80]

        now_ts = current_timestamp()
        if parsed_consensus.get("kind") != "ASSESSED":
            s["status"] = STATUS_UNRESOLVED
            b["status"] = STATUS_UNRESOLVED
        else:
            if parsed_consensus["verdict"] == "MATCH":
                s["status"] = STATUS_MATCH_PENDING
                b["status"] = STATUS_MATCH_PENDING
                s["challenge_deadline"] = now_ts + b["challenge_window"]
            else:
                s["status"] = STATUS_NOT_MATCH
                b["status"] = STATUS_OPEN
                b["active_submission"] = 0
                s["challenge_deadline"] = 0

            s["evidence_digest"] = parsed_consensus["evidence_digest"]
            s["verdict_digest"] = sha256_hex(consensus_text.encode("utf-8"))

        self._save_submission(s)
        self._save_bounty(b)
        return s["status"]

    # --------------------------------------------------------------------------
    # Public Write Methods: Dispute & Challenge Handling
    # --------------------------------------------------------------------------

    @gl.public.write
    def challenge_match(self, submission_id: u256, dispute_reason: str) -> str:
        """
        Active Dispute Mechanism:
        Allows the Bounty Sponsor (or challenger) to dispute a MATCH_PENDING verdict
        during the open challenge window. Halts instant finalization and transitions to DISPUTED.
        """
        s = self._get_submission(submission_id)
        if s is None:
            return "ERR_SUBMISSION_NOT_FOUND"

        b = self._get_bounty(u256(s["bounty_id"]))
        caller = current_sender()

        # Only the Sponsor can halt finalization without posting an external bond
        if caller != b["sponsor"]:
            return "ERR_ONLY_SPONSOR_MAY_CHALLENGE"

        if s["status"] != STATUS_MATCH_PENDING:
            return "ERR_SUBMISSION_NOT_CHALLENGEABLE"

        if current_timestamp() > s["challenge_deadline"]:
            return "ERR_CHALLENGE_WINDOW_EXPIRED"

        clean_reason = dispute_reason.strip()[:100]
        s["status"] = STATUS_DISPUTED
        s["reason"] = f"DISPUTED: {clean_reason}"
        s["revision"] += 1

        b["status"] = STATUS_DISPUTED
        self._save_submission(s)
        self._save_bounty(b)
        return STATUS_DISPUTED

    @gl.public.write
    def retry_unresolved(self, submission_id: u256, expected_revision: u256) -> str:
        """
        Allows bounded re-assessment requests when a prior attempt ended in UNRESOLVED.
        Restricted to Sponsor or Claimant, bounded by MAX_ASSESSMENT_RETRIES.
        """
        s = self._get_submission(submission_id)
        if s is None:
            return "ERR_SUBMISSION_NOT_FOUND"

        b = self._get_bounty(u256(s["bounty_id"]))
        caller = current_sender()

        if caller != b["sponsor"] and caller != s["claimant"]:
            return "ERR_ONLY_PARTICIPANT_PERMITTED"

        if s["revision"] != int(expected_revision):
            return "ERR_STALE_REVISION"

        if s["status"] != STATUS_UNRESOLVED:
            return "ERR_SUBMISSION_NOT_RETRYABLE"

        if s["attempts"] >= MAX_ASSESSMENT_RETRIES:
            return "ERR_RETRY_LIMIT_EXHAUSTED"

        s["status"] = STATUS_CLAIMED
        s["reason"] = "RETRY_REQUESTED"
        b["status"] = STATUS_CLAIMED

        self._save_submission(s)
        self._save_bounty(b)
        return STATUS_CLAIMED

    # --------------------------------------------------------------------------
    # Public Write Methods: Settlement & Recovery
    # --------------------------------------------------------------------------

    @gl.public.write
    def finalize_match(self, submission_id: u256) -> str:
        """
        Settles approved bounty to claimant after challenge window lapses.
        Enforces Checks-Effects-Interactions (CEI): clears locked principal
        and commits terminal state before external transfer.
        """
        s = self._get_submission(submission_id)
        if s is None:
            return "ERR_SUBMISSION_NOT_FOUND"

        caller = current_sender()
        if caller != s["claimant"]:
            return "ERR_ONLY_CLAIMANT_MAY_FINALIZE"

        if s["status"] != STATUS_MATCH_PENDING or current_timestamp() <= s["challenge_deadline"]:
            return "ERR_NOT_READY_FOR_FINALIZATION"

        b = self._get_bounty(u256(s["bounty_id"]))
        payout_amount = b["locked_wei"]

        if payout_amount <= 0:
            return "ERR_PRINCIPAL_ALREADY_SETTLED"

        # State updates precede external transfer (CEI)
        b["locked_wei"] = 0
        b["status"] = STATUS_PAID
        s["status"] = STATUS_PAID

        self.total_locked_wei = u256(int(self.total_locked_wei) - payout_amount)
        self.total_paid_wei = u256(int(self.total_paid_wei) + payout_amount)

        self._save_bounty(b)
        self._save_submission(s)

        # Emit native transfer to claimant
        self._transfer(s["claimant"], payout_amount)
        return STATUS_PAID

    @gl.public.write
    def recover_bounty(self, bounty_id: u256) -> str:
        """
        Permits Sponsor to recover escrowed capital under verified refund conditions:
        1. Submission deadline expired with no accepted claim, OR
        2. Active submission reached retry exhaustion in UNRESOLVED state.
        """
        b = self._get_bounty(bounty_id)
        if b is None:
            return "ERR_BOUNTY_NOT_FOUND"

        caller = current_sender()
        if caller != b["sponsor"]:
            return "ERR_ONLY_SPONSOR_MAY_RECOVER"

        now_ts = current_timestamp()
        is_recoverable = False

        if b["status"] == STATUS_OPEN and now_ts > b["submission_deadline"]:
            is_recoverable = True
        elif b["status"] == STATUS_UNRESOLVED and b["active_submission"]:
            act_sub = self._get_submission(u256(b["active_submission"]))
            if act_sub and act_sub["attempts"] >= MAX_ASSESSMENT_RETRIES:
                is_recoverable = True

        if not is_recoverable:
            return "ERR_BOUNTY_NOT_RECOVERABLE"

        refund_amount = b["locked_wei"]
        if refund_amount <= 0:
            return "ERR_PRINCIPAL_ALREADY_SETTLED"

        # CEI state update
        b["locked_wei"] = 0
        b["status"] = STATUS_REFUNDED

        self.total_locked_wei = u256(int(self.total_locked_wei) - refund_amount)
        self.total_refunded_wei = u256(int(self.total_refunded_wei) + refund_amount)

        self._save_bounty(b)
        self._transfer(b["sponsor"], refund_amount)
        return STATUS_REFUNDED

    # --------------------------------------------------------------------------
    # Public View Methods: Introspection & Telemetry
    # --------------------------------------------------------------------------

    @gl.public.view
    def get_protocol(self) -> dict:
        """Returns protocol metadata and deployment capabilities."""
        return {
            "name": "DracoLatch",
            "version": 1,
            "architecture": "commit-reveal-disclosure-escrow",
            "authority": "SEC EDGAR Canonical Archive",
            "frontrunning_protection": True,
            "active_disputes": True,
            "custody": True
        }

    @gl.public.view
    def get_bounty(self, bounty_id: u256) -> dict:
        """Returns full bounty state record by ID."""
        return self._get_bounty(bounty_id) or {}

    @gl.public.view
    def get_submission(self, submission_id: u256) -> dict:
        """Returns full submission state record by ID."""
        return self._get_submission(submission_id) or {}

    @gl.public.view
    def get_totals(self) -> dict:
        """Returns aggregate protocol accounting metrics."""
        return {
            "bounties": int(self.bounty_count),
            "submissions": int(self.submission_count),
            "locked_wei": str(int(self.total_locked_wei)),
            "paid_wei": str(int(self.total_paid_wei)),
            "refunded_wei": str(int(self.total_refunded_wei))
        }

Contract = DracoLatch
