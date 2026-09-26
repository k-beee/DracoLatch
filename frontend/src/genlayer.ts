import { createClient } from 'genlayer-js';
import { studioDevnet, studionet } from 'genlayer-js/chains';
import type { CalldataEncodable, TransactionHash } from 'genlayer-js/types';

export const CONTRACT_ADDRESS = (import.meta.env.VITE_CONTRACT_ADDRESS || '').trim();
export const IS_CONFIGURED = /^0x[a-fA-F0-9]{40}$/.test(CONTRACT_ADDRESS);

export const SELECTED_CHAIN = (import.meta.env.VITE_GENLAYER_NETWORK || 'studioDevnet') === 'studionet' 
  ? studionet 
  : studioDevnet;

export const EXPLORER_BASE = SELECTED_CHAIN.id === 61997
  ? 'https://explorer-studio-dev.genlayer.com'
  : 'https://explorer-studio.genlayer.com';

export const contractExplorerUrl = IS_CONFIGURED 
  ? `${EXPLORER_BASE}/address/${CONTRACT_ADDRESS}` 
  : '';

export const txExplorerUrl = (txHash: string) => `${EXPLORER_BASE}/tx/${txHash}`;

export const readerClient = createClient({ chain: SELECTED_CHAIN });

export const getWriterClient = () => {
  if (!window.ethereum) {
    throw new Error('Please install and connect MetaMask or another EIP-1193 compatible wallet.');
  }
  return createClient({ chain: SELECTED_CHAIN, provider: window.ethereum });
};

export const formatAddress = (addr?: string) => {
  if (!addr) return '—';
  const clean = addr.trim();
  if (clean.length < 10) return clean;
  return `${clean.slice(0, 6)}...${clean.slice(-4)}`;
};

export const weiToGen = (weiStr?: string | number | bigint) => {
  if (!weiStr) return '0.00 GEN';
  try {
    const val = BigInt(weiStr);
    const whole = val / 10n**18n;
    const rem = val % 10n**18n;
    const dec = (rem / 10n**14n).toString().padStart(4, '0');
    return `${whole}.${dec} GEN`;
  } catch {
    return '0.00 GEN';
  }
};

export const genToWei = (genStr: string): bigint => {
  const parsed = parseFloat(genStr);
  if (isNaN(parsed) || parsed <= 0) return 0n;
  return BigInt(Math.round(parsed * 1e6)) * 10n**12n;
};

export const normalizeTxHash = (result: unknown): string => {
  if (typeof result === 'string') return result;
  if (result && typeof result === 'object' && 'txId' in result) {
    return String((result as { txId?: string }).txId || '');
  }
  return String(result || '');
};
