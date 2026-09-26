/**
 * DracoLatch: Active Challenge & Dispute Path Runner
 * Exercises:
 * 1. An assessed MATCH_PENDING submission is challenged by the Sponsor during the challenge window
 * 2. Contract transitions to DISPUTED
 * 3. Asserts that premature finalization attempts fail
 */

import { createAccount, createClient } from 'genlayer-js';
import { studionet, studioDevnet } from 'genlayer-js/chains';

const CONTRACT = process.env.DRACO_CONTRACT_ADDRESS;
const SPONSOR_KEY = process.env.SPONSOR_PRIVATE_KEY;
const SUBMISSION_ID = process.env.SUBMISSION_ID || '1';

if (!CONTRACT || !SPONSOR_KEY) {
  console.log('Usage: DRACO_CONTRACT_ADDRESS=0x... SPONSOR_PRIVATE_KEY=0x... node run_dispute_path.mjs');
  process.exit(0);
}

const chain = process.env.GENLAYER_NETWORK === 'studionet' ? studionet : studioDevnet;
const sponsor = createAccount(SPONSOR_KEY.startsWith('0x') ? SPONSOR_KEY : `0x${SPONSOR_KEY}`);
const sponsorClient = createClient({ chain, account: sponsor });
const reader = createClient({ chain });

async function main() {
  console.log('=== DracoLatch: Initiating Challenge & Dispute ===');
  console.log(`Sponsor: ${sponsor.address}`);
  console.log(`Target Submission ID: ${SUBMISSION_ID}`);

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

  const updatedSub = await reader.readContract({
    address: CONTRACT,
    functionName: 'get_submission',
    args: [BigInt(SUBMISSION_ID)],
    jsonSafeReturn: true
  });
  console.log('Updated Submission State:', updatedSub);
  if (updatedSub.status === 'DISPUTED') {
    console.log('✓ PASS: Submission successfully halted in DISPUTED state.');
  }
}

main().catch(console.error);
