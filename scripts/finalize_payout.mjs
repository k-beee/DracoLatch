/**
 * DracoLatch: Payout Finalization Runner
 * Invoked by claimant after challenge window has lapsed to claim reward.
 */

import { createAccount, createClient } from 'genlayer-js';
import { studionet, studioDevnet } from 'genlayer-js/chains';

const CONTRACT = process.env.DRACO_CONTRACT_ADDRESS;
const CLAIMANT_KEY = process.env.CLAIMANT_PRIVATE_KEY;
const SUBMISSION_ID = process.env.SUBMISSION_ID || '1';

if (!CONTRACT || !CLAIMANT_KEY) {
  console.log('Usage: DRACO_CONTRACT_ADDRESS=0x... CLAIMANT_PRIVATE_KEY=0x... node finalize_payout.mjs');
  process.exit(0);
}

const chain = process.env.GENLAYER_NETWORK === 'studionet' ? studionet : studioDevnet;
const claimant = createAccount(CLAIMANT_KEY.startsWith('0x') ? CLAIMANT_KEY : `0x${CLAIMANT_KEY}`);
const claimantClient = createClient({ chain, account: claimant });
const reader = createClient({ chain });

async function main() {
  console.log('=== DracoLatch: Finalizing Payout ===');
  console.log(`Claimant: ${claimant.address}`);
  console.log(`Submission ID: ${SUBMISSION_ID}`);

  const finalizeTx = await claimantClient.writeContract({
    address: CONTRACT,
    functionName: 'finalize_match',
    args: [BigInt(SUBMISSION_ID)]
  });
  console.log(`Finalize Tx: ${finalizeTx}`);
  await reader.waitForTransactionReceipt({ hash: finalizeTx, waitUntil: 'finalized' });

  const totals = await reader.readContract({
    address: CONTRACT,
    functionName: 'get_totals',
    jsonSafeReturn: true
  });
  console.log('Accounting Totals after Settlement:', totals);
}

main().catch(console.error);
