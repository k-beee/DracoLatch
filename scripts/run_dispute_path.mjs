/**
 * DracoLatch: Active Challenge & Dispute Path Runner
 * Exercises:
 * 1. An assessed MATCH_PENDING submission is challenged by the Sponsor during the challenge window
 * 2. Contract transitions to DISPUTED
 * 3. Supports appellate adjudication (adjudicate_dispute) to reach Hunter Payout or Sponsor Recovery
 * 4. Supports voluntary challenge withdrawal (withdraw_challenge)
 */

import { createAccount, createClient } from 'genlayer-js';
import { studionet, studioDevnet } from 'genlayer-js/chains';

const CONTRACT = process.env.DRACO_CONTRACT_ADDRESS;
const SPONSOR_KEY = process.env.SPONSOR_PRIVATE_KEY;
const SUBMISSION_ID = process.env.SUBMISSION_ID || '1';
const ACTION = process.env.ACTION || 'challenge'; // 'challenge' | 'adjudicate' | 'withdraw'

if (!CONTRACT || !SPONSOR_KEY) {
  console.log('Usage: DRACO_CONTRACT_ADDRESS=0x... SPONSOR_PRIVATE_KEY=0x... [ACTION=challenge|adjudicate|withdraw] node run_dispute_path.mjs');
  process.exit(0);
}

const chain = process.env.GENLAYER_NETWORK === 'studionet' ? studionet : studioDevnet;
const sponsor = createAccount(SPONSOR_KEY.startsWith('0x') ? SPONSOR_KEY : `0x${SPONSOR_KEY}`);
const sponsorClient = createClient({ chain, account: sponsor });
const reader = createClient({ chain });

async function main() {
  console.log('=== DracoLatch: Dispute & Adjudication Runner ===');
  console.log(`Sponsor: ${sponsor.address}`);
  console.log(`Target Submission ID: ${SUBMISSION_ID}`);
  console.log(`Action: ${ACTION}`);

  if (ACTION === 'challenge') {
    const challengeTx = await sponsorClient.writeContract({
      address: CONTRACT,
      functionName: 'challenge_match',
      args: [
        BigInt(SUBMISSION_ID),
        'Filing text fails to substantively cover required executive duties'
      ]
    });
    console.log(`Challenge Tx: ${challengeTx}`);
    await reader.waitForTransactionReceipt({ hash: challengeTx, waitUntil: 'finalized' });
  } else if (ACTION === 'adjudicate') {
    const sub = await reader.readContract({
      address: CONTRACT,
      functionName: 'get_submission',
      args: [BigInt(SUBMISSION_ID)],
      jsonSafeReturn: true
    });
    const rev = BigInt(sub.revision || 1);
    console.log(`Triggering appellate adjudication at revision ${rev}...`);
    const adjTx = await sponsorClient.writeContract({
      address: CONTRACT,
      functionName: 'adjudicate_dispute',
      args: [BigInt(SUBMISSION_ID), rev]
    });
    console.log(`Adjudication Tx: ${adjTx}`);
    await reader.waitForTransactionReceipt({ hash: adjTx, waitUntil: 'finalized' });
  } else if (ACTION === 'withdraw') {
    console.log('Withdrawing dispute challenge...');
    const withdrawTx = await sponsorClient.writeContract({
      address: CONTRACT,
      functionName: 'withdraw_challenge',
      args: [BigInt(SUBMISSION_ID)]
    });
    console.log(`Withdraw Tx: ${withdrawTx}`);
    await reader.waitForTransactionReceipt({ hash: withdrawTx, waitUntil: 'finalized' });
  }

  const updatedSub = await reader.readContract({
    address: CONTRACT,
    functionName: 'get_submission',
    args: [BigInt(SUBMISSION_ID)],
    jsonSafeReturn: true
  });
  console.log('\nUpdated Submission State:', updatedSub);
}

main().catch(console.error);
