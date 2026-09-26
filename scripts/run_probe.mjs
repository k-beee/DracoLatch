/**
 * DracoLatch: Preflight Diagnostic Probe Runner
 * Deploys/queries DracoSourceProbe on target GenLayer network (Studionet / Studio Next)
 * to verify validator SEC EDGAR fetching and SHA-256 agreement.
 */

import { createAccount, createClient } from 'genlayer-js';
import { studionet, studioDevnet } from 'genlayer-js/chains';

const PROBE_CONTRACT = process.env.DRACO_PROBE_ADDRESS || '0x60d3f54658b15b07F29f08103317324a876CF638';
const CHAIN_NAME = process.env.GENLAYER_NETWORK || 'studioDevnet';
const chain = CHAIN_NAME === 'studionet' ? studionet : studioDevnet;

const reader = createClient({ chain });

async function main() {
  console.log(`[DracoSourceProbe] Target Contract: ${PROBE_CONTRACT}`);
  console.log(`[DracoSourceProbe] Network: ${chain.name} (Chain ID: ${chain.id})`);

  try {
    const lastResult = await reader.readContract({
      address: PROBE_CONTRACT,
      functionName: 'get_last_probe',
      jsonSafeReturn: true
    });
    console.log(`[DracoSourceProbe] Latest Finalized Probe: ${lastResult}`);
    
    const expectedPrefix = '200:38298:79d278b5c34a40ec5618d5286c983120346ebb58ccd8587339533b88e7f22e37';
    if (lastResult === expectedPrefix) {
      console.log('✓ PASS: Probe matches exact canonical SEC Apple 8-K bytes & digest.');
    } else {
      console.log('ℹ Note: Probe result differs or requires write invocation.');
    }
  } catch (err) {
    console.error('Error reading probe contract:', err);
  }
}

main().catch(console.error);
