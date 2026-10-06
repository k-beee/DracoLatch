import React, { useState, useEffect, useRef } from 'react';
import { 
  ShieldCheck, 
  Lock, 
  Key, 
  FileText, 
  ExternalLink, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Flame, 
  Scale, 
  Search, 
  Wallet,
  Sparkles,
  Layers
} from 'lucide-react';
import type { CalldataEncodable, TransactionHash } from 'genlayer-js/types';
import { 
  CONTRACT_ADDRESS, 
  IS_CONFIGURED, 
  contractExplorerUrl, 
  txExplorerUrl, 
  readerClient, 
  getWriterClient, 
  formatAddress, 
  weiToGen, 
  genToWei, 
  normalizeTxHash,
  SELECTED_CHAIN
} from './genlayer';

interface LogItem {
  id: string;
  label: string;
  txHash: string;
  timestamp: string;
}

const DEFAULT_FIXTURE = {
  title: 'Apple COO Succession Disclosure',
  requirement: "Confirm a planned COO succession naming the successor and the outgoing executive's transition duties.",
  cik: '0000320193',
  form: '8-K',
  accession: '0001140361-25-025275',
  document: 'ef20051741_8k.htm',
  digest: '79d278b5c34a40ec5618d5286c983120346ebb58ccd8587339533b88e7f22e37'
};

export default function App() {
  const [account, setAccount] = useState<string>('');
  const [protocol, setProtocol] = useState<any>(null);
  const [totals, setTotals] = useState<any>(null);
  const [bounty, setBounty] = useState<any>(null);
  const [submission, setSubmission] = useState<any>(null);
  
  const [bountyId, setBountyId] = useState<string>('1');
  const [submissionId, setSubmissionId] = useState<string>('1');
  const [bountyAmount, setBountyAmount] = useState<string>('0.01');
  
  // Claim form states
  const [claimMode, setClaimMode] = useState<'commit' | 'direct'>('commit');
  const [salt, setSalt] = useState<string>('draco_salt_' + Math.floor(Math.random() * 10000));
  const [disputeReason, setDisputeReason] = useState<string>('Material disclosure requirement omitted in filing excerpt.');
  
  const [isBusy, setIsBusy] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [activityLogs, setActivityLogs] = useState<LogItem[]>([]);
  
  const syncSeq = useRef<number>(0);

  // Sync state over RPC
  const syncState = async () => {
    if (!IS_CONFIGURED) return;
    const seq = ++syncSeq.current;
    setErrorMessage('');

    const readSafe = async (fn: string, args: CalldataEncodable[] = []) => {
      let lastErr: unknown;
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          return await readerClient.readContract({
            address: CONTRACT_ADDRESS,
            functionName: fn,
            args,
            jsonSafeReturn: true
          });
        } catch (err) {
          lastErr = err;
          if (attempt < 2) await new Promise((r) => setTimeout(r, 600 * (attempt + 1)));
        }
      }
      throw lastErr;
    };

    try {
      const bid = Number(bountyId);
      const sid = Number(submissionId);

      const [p, t] = await Promise.all([
        readSafe('get_protocol'),
        readSafe('get_totals')
      ]);

      const b = bid > 0 ? await readSafe('get_bounty', [bid]) : null;
      const s = sid > 0 ? await readSafe('get_submission', [sid]) : null;

      if (seq !== syncSeq.current) return;
      setProtocol(p);
      setTotals(t);
      setBounty(b);
      setSubmission(s);
    } catch (err) {
      if (seq === syncSeq.current) {
        setErrorMessage(err instanceof Error ? err.message : String(err));
      }
    }
  };

  useEffect(() => {
    if (IS_CONFIGURED) {
      void syncState();
    }
  }, []);

  const connectWallet = async () => {
    if (!window.ethereum) {
      setErrorMessage('No injected Web3 wallet found. Please install MetaMask or Rabby.');
      return;
    }
    try {
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' }) as string[];
      if (accounts && accounts[0]) {
        setAccount(accounts[0]);
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
    }
  };

  const executeTx = async (label: string, fn: string, args: CalldataEncodable[], valueWei: bigint = 0n) => {
    setIsBusy(label);
    setErrorMessage('');
    try {
      const client = getWriterClient();
      const fees = await client.estimateTransactionFees({});
      const rawTx = await client.writeContract({
        address: CONTRACT_ADDRESS,
        functionName: fn,
        args,
        value: valueWei,
        fees
      });

      const txHash = normalizeTxHash(rawTx);
      const newLog: LogItem = {
        id: Math.random().toString(),
        label,
        txHash,
        timestamp: new Date().toLocaleTimeString()
      };
      setActivityLogs((prev) => [newLog, ...prev]);

      await readerClient.waitForTransactionReceipt({
        hash: txHash as TransactionHash,
        waitUntil: 'finalized',
        interval: 3500,
        retries: 300
      });

      await syncState();
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setIsBusy('');
    }
  };

  // Actions
  const handleCreateBounty = () => {
    const val = genToWei(bountyAmount);
    return executeTx(
      'Create Funded Bounty',
      'create_bounty',
      [
        DEFAULT_FIXTURE.title,
        DEFAULT_FIXTURE.requirement,
        DEFAULT_FIXTURE.cik,
        DEFAULT_FIXTURE.form,
        1700000000n,
        1800000000n,
        86400n,
        300n
      ],
      val
    );
  };

  const handleCommitClaim = async () => {
    if (!account) {
      setErrorMessage('Please connect your wallet first.');
      return;
    }
    // sha256(claimant:accession:salt)
    const encoder = new TextEncoder();
    const data = encoder.encode(`${account.toLowerCase()}:${DEFAULT_FIXTURE.accession}:${salt}`);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const commitmentHash = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');

    return executeTx(
      'Commit Claim (Anti-Frontrun)',
      'commit_claim',
      [Number(bountyId), commitmentHash]
    );
  };

  const handleRevealClaim = () => {
    return executeTx(
      'Reveal & Submit Filing',
      'reveal_and_submit',
      [
        Number(bountyId),
        DEFAULT_FIXTURE.accession,
        DEFAULT_FIXTURE.document,
        DEFAULT_FIXTURE.digest,
        salt
      ]
    );
  };

  const handleSubmitDirect = () => {
    return executeTx(
      'Submit Direct Filing',
      'submit_direct',
      [
        Number(bountyId),
        DEFAULT_FIXTURE.accession,
        DEFAULT_FIXTURE.document,
        DEFAULT_FIXTURE.digest
      ]
    );
  };

  const handleAssessSubmission = () => {
    const rev = Number(submission?.revision || 1);
    return executeTx(
      'Assess Evidence (Validators)',
      'assess_submission',
      [Number(submissionId), rev]
    );
  };

  const handleChallengeMatch = () => {
    return executeTx(
      'Challenge Match (Dispute)',
      'challenge_match',
      [Number(submissionId), disputeReason]
    );
  };

  const handleAdjudicateDispute = () => {
    const rev = Number(submission?.revision || 1);
    return executeTx(
      'Adjudicate Dispute (Validators)',
      'adjudicate_dispute',
      [Number(submissionId), rev]
    );
  };

  const handleWithdrawChallenge = () => {
    return executeTx(
      'Withdraw Dispute (Sponsor)',
      'withdraw_challenge',
      [Number(submissionId)]
    );
  };

  const handleFinalizeMatch = () => {
    return executeTx(
      'Finalize Payout (Claimant)',
      'finalize_match',
      [Number(submissionId)]
    );
  };

  const handleRecoverBounty = () => {
    return executeTx(
      'Recover Bounty (Sponsor)',
      'recover_bounty',
      [Number(bountyId)]
    );
  };

  return (
    <>
      <header>
        <div className="brand">
          <div className="brand-icon">
            <Flame size={24} />
          </div>
          <div className="brand-title">
            DracoLatch
            <span className="brand-subtitle">Autonomous Disclosure Escrow</span>
          </div>
        </div>

        <div className="header-right">
          <div className="network-badge">
            <span className="status-dot"></span>
            {SELECTED_CHAIN.name} (Chain {SELECTED_CHAIN.id})
          </div>

          <button className="btn-secondary" onClick={connectWallet}>
            <Wallet size={16} />
            {account ? formatAddress(account) : 'Connect Wallet'}
          </button>
        </div>
      </header>

      <main>
        {/* Hero Section */}
        <section className="hero">
          <div className="hero-pill">
            <ShieldCheck size={14} /> Sovereign SEC EDGAR Verification Latch
          </div>
          <h1>
            Turn Authoritative Filings into <span>Cryptographic Escrow Proof.</span>
          </h1>
          <p className="hero-lead">
            Fund high-stakes public company disclosure bounties. Evidence hunters submit official SEC filings with 
            commit-reveal anti-frontrunning protection. GenLayer Intelligent Validators verify byte digests and natural language compliance.
          </p>

          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <a href="#console" className="btn-primary" style={{ width: 'auto' }}>
              Enter Evidence Console
            </a>
            {contractExplorerUrl && (
              <a href={contractExplorerUrl} target="_blank" rel="noreferrer" className="btn-secondary">
                View Contract <ExternalLink size={14} />
              </a>
            )}
          </div>
        </section>

        {/* Telemetry Strip */}
        <section className="telemetry-strip">
          <div className="telemetry-card">
            <div className="telemetry-label">Active Bounties</div>
            <div className="telemetry-value">{totals?.bounties ?? '0'}</div>
          </div>
          <div className="telemetry-card">
            <div className="telemetry-label">Filings Assessed</div>
            <div className="telemetry-value">{totals?.submissions ?? '0'}</div>
          </div>
          <div className="telemetry-card">
            <div className="telemetry-label">Locked Escrow</div>
            <div className="telemetry-value">{weiToGen(totals?.locked_wei)}</div>
          </div>
          <div className="telemetry-card">
            <div className="telemetry-label">Paid to Hunters</div>
            <div className="telemetry-value" style={{ color: '#34D399' }}>{weiToGen(totals?.paid_wei)}</div>
          </div>
          <div className="telemetry-card">
            <div className="telemetry-label">Refunded Principal</div>
            <div className="telemetry-value" style={{ color: '#94A3B8' }}>{weiToGen(totals?.refunded_wei)}</div>
          </div>
        </section>

        {/* Error Banner */}
        {errorMessage && (
          <div style={{ maxWidth: '1240px', margin: '0 auto 1.5rem', padding: '0 2.5rem' }}>
            <div className="error-banner">
              <AlertTriangle size={16} style={{ display: 'inline', marginRight: '0.5rem', verticalAlign: 'text-bottom' }} />
              {errorMessage}
            </div>
          </div>
        )}

        {/* Dual Interactive Workspace Desks */}
        <section className="workspace-grid" id="console">
          {/* SPONSOR DESK */}
          <div className="vault-panel">
            <div className="vault-panel-header">
              <div className="panel-title">
                <Scale size={20} color="#10B981" />
                Sponsor Desk
              </div>
              <span className="badge badge-open">Capital Locking</span>
            </div>

            <div className="fixture-preset">
              <div className="fixture-header">
                <span className="fixture-tag">Verified SEC Preset</span>
                <span className="fixture-meta">CIK {DEFAULT_FIXTURE.cik} | Form {DEFAULT_FIXTURE.form}</span>
              </div>
              <div className="fixture-desc">{DEFAULT_FIXTURE.requirement}</div>
              <div className="fixture-meta">Target: Apple Inc. Official EDGAR Archive</div>
            </div>

            <div className="form-group">
              <label className="form-label">Escrow Bounty Amount (GEN)</label>
              <input 
                type="text" 
                value={bountyAmount} 
                onChange={(e) => setBountyAmount(e.target.value)} 
                placeholder="0.01" 
              />
            </div>

            <button 
              className="btn-primary" 
              onClick={handleCreateBounty} 
              disabled={!!isBusy}
              style={{ marginBottom: '1rem' }}
            >
              <Lock size={16} />
              {isBusy === 'Create Funded Bounty' ? 'Locking Escrow...' : 'Create Funded Bounty'}
            </button>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginTop: '1rem' }}>
              <button 
                className="btn-danger" 
                onClick={handleChallengeMatch}
                disabled={!!isBusy || bounty?.status !== 'MATCH_PENDING'}
              >
                <AlertTriangle size={15} style={{ marginRight: '4px', verticalAlign: 'text-bottom' }} />
                Dispute Match
              </button>

              <button 
                className="btn-secondary" 
                onClick={handleRecoverBounty}
                disabled={!!isBusy || !['OPEN', 'UNRESOLVED', 'CHALLENGE_UPHELD'].includes(bounty?.status || '')}
              >
                Recover Escrow
              </button>
            </div>

            {bounty?.status === 'DISPUTED' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginTop: '0.75rem' }}>
                <button 
                  className="btn-secondary" 
                  onClick={handleAdjudicateDispute}
                  disabled={!!isBusy}
                  style={{ borderColor: '#F59E0B', color: '#FCD34D' }}
                >
                  <Sparkles size={15} /> Adjudicate Dispute
                </button>
                <button 
                  className="btn-secondary" 
                  onClick={handleWithdrawChallenge}
                  disabled={!!isBusy}
                >
                  Withdraw Dispute
                </button>
              </div>
            )}
          </div>

          {/* HUNTER DESK */}
          <div className="vault-panel">
            <div className="vault-panel-header">
              <div className="panel-title">
                <Search size={20} color="#34D399" />
                Hunter Evidence Desk
              </div>

              <div className="tab-group">
                <button 
                  className={`tab-btn ${claimMode === 'commit' ? 'active' : ''}`}
                  onClick={() => setClaimMode('commit')}
                >
                  Commit-Reveal
                </button>
                <button 
                  className={`tab-btn ${claimMode === 'direct' ? 'active' : ''}`}
                  onClick={() => setClaimMode('direct')}
                >
                  Direct Claim
                </button>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Target Bounty ID</label>
              <input 
                type="number" 
                value={bountyId} 
                onChange={(e) => setBountyId(e.target.value)} 
                className="code-field"
              />
            </div>

            {claimMode === 'commit' ? (
              <>
                <div className="form-group">
                  <label className="form-label">Hunter Secret Salt (For Frontrunning Shield)</label>
                  <input 
                    type="text" 
                    value={salt} 
                    onChange={(e) => setSalt(e.target.value)} 
                    className="code-field"
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1rem' }}>
                  <button 
                    className="btn-secondary" 
                    onClick={handleCommitClaim}
                    disabled={!!isBusy}
                  >
                    <Key size={15} /> Commit Claim
                  </button>
                  <button 
                    className="btn-primary" 
                    onClick={handleRevealClaim}
                    disabled={!!isBusy}
                  >
                    <FileText size={15} /> Reveal & Submit
                  </button>
                </div>
              </>
            ) : (
              <button 
                className="btn-primary" 
                onClick={handleSubmitDirect}
                disabled={!!isBusy}
                style={{ marginBottom: '1rem' }}
              >
                <FileText size={16} /> Submit Canonical Filing
              </button>
            )}

            <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '1.25rem', marginTop: '0.5rem' }}>
              <div className="form-group">
                <label className="form-label">Submission ID to Evaluate</label>
                <input 
                  type="number" 
                  value={submissionId} 
                  onChange={(e) => setSubmissionId(e.target.value)} 
                  className="code-field"
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <button 
                  className="btn-secondary" 
                  onClick={handleAssessSubmission}
                  disabled={!!isBusy}
                >
                  <RefreshCw size={15} /> Assess Submission
                </button>
                <button 
                  className="btn-primary" 
                  onClick={handleFinalizeMatch}
                  disabled={!!isBusy || !['MATCH_PENDING', 'MATCH_UPHELD'].includes(submission?.status || '')}
                >
                  <CheckCircle2 size={15} /> Finalize Payout
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* State Inspector & Verification Gates */}
        <section className="state-viewer">
          <div className="state-card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '1.25rem' }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Layers size={20} color="#10B981" />
                  Live On-Chain State Inspector
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Inspect real-time consensus telemetry, cryptographic commitments, and dispute records.
                </p>
              </div>

              <button className="btn-secondary" onClick={syncState} disabled={!!isBusy}>
                <RefreshCw size={15} /> Refresh State
              </button>
            </div>

            <div className="state-grid">
              <div className="state-entry">
                <div className="state-entry-label">Bounty Status</div>
                <div className="state-entry-val">
                  <span className={`badge ${bounty?.status === 'PAID' ? 'badge-paid' : bounty?.status === 'MATCH_PENDING' ? 'badge-pending' : 'badge-open'}`}>
                    {bounty?.status || 'NOT LOADED'}
                  </span>
                </div>
              </div>

              <div className="state-entry">
                <div className="state-entry-label">Submission Verdict</div>
                <div className="state-entry-val">
                  <span className={`badge ${submission?.status === 'PAID' ? 'badge-paid' : submission?.status === 'MATCH_PENDING' ? 'badge-pending' : submission?.status === 'DISPUTED' ? 'badge-disputed' : 'badge-open'}`}>
                    {submission?.status || 'NOT LOADED'}
                  </span>
                </div>
              </div>

              <div className="state-entry">
                <div className="state-entry-label">Normalized Reason Code</div>
                <div className="state-entry-val" style={{ color: '#34D399' }}>
                  {submission?.reason || 'NONE'}
                </div>
              </div>

              <div className="state-entry">
                <div className="state-entry-label">Bounty Sponsor</div>
                <div className="state-entry-val">{formatAddress(bounty?.sponsor)}</div>
              </div>

              <div className="state-entry">
                <div className="state-entry-label">Claimant Address</div>
                <div className="state-entry-val">{formatAddress(submission?.claimant)}</div>
              </div>

              <div className="state-entry">
                <div className="state-entry-label">SEC Accession Number</div>
                <div className="state-entry-val">{submission?.accession || '—'}</div>
              </div>

              <div className="state-entry" style={{ gridColumn: 'span 2' }}>
                <div className="state-entry-label">Verified SHA-256 Digest</div>
                <div className="state-entry-val" style={{ fontSize: '0.78rem' }}>
                  {submission?.evidence_digest || submission?.expected_sha256 || '—'}
                </div>
              </div>
            </div>

            {/* Verification Gates Diagram */}
            <div style={{ marginTop: '2rem', padding: '1.5rem', background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                Validator Multi-Gate Settlement Protocol
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                <div style={{ padding: '0.85rem', background: 'var(--bg-surface)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>GATE 1</div>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem' }}>Byte Digest Preflight</div>
                  <div style={{ fontSize: '0.75rem', color: submission?.evidence_digest ? '#34D399' : 'var(--text-muted)' }}>
                    {submission?.evidence_digest ? '✓ Digest Confirmed' : 'Pending Verification'}
                  </div>
                </div>

                <div style={{ padding: '0.85rem', background: 'var(--bg-surface)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>GATE 2</div>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem' }}>Provenance Invariant</div>
                  <div style={{ fontSize: '0.75rem', color: submission?.status ? '#34D399' : 'var(--text-muted)' }}>
                    {submission?.status && submission.status !== 'UNRESOLVED' ? '✓ Headers Validated' : 'Pending Verification'}
                  </div>
                </div>

                <div style={{ padding: '0.85rem', background: 'var(--bg-surface)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>GATE 3</div>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem' }}>Comparative Consensus</div>
                  <div style={{ fontSize: '0.75rem', color: submission?.status === 'MATCH_PENDING' || submission?.status === 'PAID' ? '#34D399' : 'var(--text-muted)' }}>
                    {submission?.status === 'MATCH_PENDING' || submission?.status === 'PAID' ? '✓ Verdict Confirmed' : 'Pending Consensus'}
                  </div>
                </div>

                <div style={{ padding: '0.85rem', background: 'var(--bg-surface)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>GATE 4</div>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem' }}>Challenge Window</div>
                  <div style={{ fontSize: '0.75rem', color: submission?.status === 'PAID' ? '#34D399' : 'var(--text-muted)' }}>
                    {submission?.status === 'PAID' ? '✓ Escrow Disbursed' : 'Awaiting Finality'}
                  </div>
                </div>
              </div>
            </div>

            {/* Transaction Activity Feed */}
            {activityLogs.length > 0 && (
              <div className="activity-log">
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.75rem' }}>
                  Live Session Transaction Feed
                </div>
                {activityLogs.map((log) => (
                  <div key={log.id} className="log-item">
                    <span>{log.label} <small style={{ color: 'var(--text-muted)' }}>({log.timestamp})</small></span>
                    <a href={txExplorerUrl(log.txHash)} target="_blank" rel="noreferrer" className="log-hash">
                      {log.txHash.slice(0, 10)}...{log.txHash.slice(-8)} <ExternalLink size={12} style={{ display: 'inline', verticalAlign: 'text-bottom' }} />
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </main>

      <footer>
        <p><strong>DracoLatch</strong> &copy; 2026. Built natively for GenLayer Intelligent Contracts.</p>
        <p style={{ marginTop: '0.35rem', fontSize: '0.8rem' }}>
          Official SEC EDGAR Authority. Commit-Reveal Anti-Frontrunning. Comparative Validator Consensus.
        </p>
      </footer>
    </>
  );
}
