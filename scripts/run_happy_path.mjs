/**
 * DracoLatch: Happy Path Lifecycle Automation
 * Exercises:
 * 1. Sponsor funds a bounty with locked GEN
 * 2. Hunter commits claim hash: sha256(claimant + accession + salt)
 * 3. Hunter reveals accession, document name, and SHA-256 digest
 * 4. Sponsor/Claimant triggers validator assessment
 * 5. Validators fetch SEC EDGAR, verify digest, evaluate semantic match
 * 6. Challenge window passes
 * 7. Claimant finalizes match and receives payout
 */

import { createAccount, createClient } from 'genlayer-js';
import { studionet, studioDevnet } from 'genlayer-js/chains';
import crypto from 'crypto';

const CONTRACT = process.env.DRACO_CONTRACT_ADDRESS;
const SPONSOR_KEY = process.env.SPONSOR_PRIVATE_KEY;
const CLAIMANT_KEY = process.env.CLAIMANT_PRIVATE_KEY;

if (!CONTRACT || !SPONSOR_KEY || !CLAIMANT_KEY) {
  console.log('Usage: DRACO_CONTRACT_ADDRESS=0x... SPONSOR_PRIVATE_KEY=0x... CLAIMANT_PRIVATE_KEY=0x... node run_happy_path.mjs');
  process.exit(0);
}

const chain = process.env.GENLAYER_NETWORK === 'studionet' ? studionet : studioDevnet;
const sponsor = createAccount(SPONSOR_KEY.startsWith('0x') ? SPONSOR_KEY : `0x${SPONSOR_KEY}`);
const claimant = createAccount(CLAIMANT_KEY.startsWith('0x') ? CLAIMANT_KEY : `0x${CLAIMANT_KEY}`);

const sponsorClient = createClient({ chain, account: sponsor });
const claimantClient = createClient({ chain, account: claimant });
const reader = createClient({ chain });

async function main() {
  console.log('=== DracoLatch: Initiating Happy Path ===');
  console.log(`Sponsor: ${sponsor.address}`);
  console.log(`Claimant: ${claimant.address}`);

  // 1. Create Bounty
  console.log('\n[Step 1] Creating funded disclosure bounty (0.01 GEN)...');
  const createTx = await sponsorClient.writeContract({
    address: CONTRACT,
    functionName: 'create_bounty',
    args: [
      'Apple COO Succession Disclosure',
      "Confirm a planned COO succession naming the successor and the outgoing executive's transition duties.",
      '0000320193',
      '8-K',
      1700000000n,
      1800000000n,
      86400n,
      300n
    ],
    value: 10n**16n
  });
  console.log(`Create Tx: ${createTx}`);
  await reader.waitForTransactionReceipt({ hash: createTx, waitUntil: 'finalized' });

  // 2. Commit Claim
  console.log('\n[Step 2] Hunter commits claim hash (Anti-Frontrunning)...');
  const accession = '0001140361-25-025275';
  const doc = 'ef20051741_8k.htm';
  const digest = '79d278b5c34a40ec5618d5286c983120346ebb58ccd8587339533b88e7f22e37';
  const salt = 'salt_' + Date.now();
  const commitHash = crypto.createHash('sha256').update(`${claimant.address.toLowerCase()}:${accession}:${salt}`).digest('hex');

  const commitTx = await claimantClient.writeContract({
    address: CONTRACT,
    functionName: 'commit_claim',
    args: [1n, commitHash]
  });
  console.log(`Commit Tx: ${commitTx}`);
  await reader.waitForTransactionReceipt({ hash: commitTx, waitUntil: 'finalized' });

  // 3. Reveal and Submit
  console.log('\n[Step 3] Hunter reveals accession, doc, digest and salt...');
  const revealTx = await claimantClient.writeContract({
    address: CONTRACT,
    functionName: 'reveal_and_submit',
    args: [1n, accession, doc, digest, salt]
  });
  console.log(`Reveal Tx: ${revealTx}`);
  await reader.waitForTransactionReceipt({ hash: revealTx, waitUntil: 'finalized' });

  // 4. Assess Submission
  console.log('\n[Step 4] Triggering multi-validator SEC evaluation...');
  const assessTx = await sponsorClient.writeContract({
    address: CONTRACT,
    functionName: 'assess_submission',
    args: [1n, 1n]
  });
  console.log(`Assess Tx: ${assessTx}`);
  await reader.waitForTransactionReceipt({ hash: assessTx, waitUntil: 'finalized' });

  const submissionState = await reader.readContract({
    address: CONTRACT,
    functionName: 'get_submission',
    args: [1n],
    jsonSafeReturn: true
  });
  console.log('Submission State:', submissionState);
  console.log('=== Happy Path Prepared for Finalization after Challenge Window ===');
}

main().catch(console.error);
