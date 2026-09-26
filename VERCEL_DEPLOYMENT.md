# Deploying DracoLatch to Vercel

This guide explains how to deploy the **DracoLatch Obsidian Vault dApp** to Vercel in under 2 minutes.

---

## Option 1: 1-Click Dashboard Import (Recommended)

1. Go to [vercel.com/new](https://vercel.com/new).
2. Select your repository: **`k-beee/DracoLatch`**.
3. Vercel automatically reads [`vercel.json`](vercel.json) from the repository root:
   - **Framework Preset:** Vite
   - **Root Directory:** `./` (Leave as default, or select `frontend`—both are supported)
   - **Build Command:** `npm run build` (or `cd frontend && npm install && npm run build`)
   - **Output Directory:** `frontend/dist` (or `dist` if `frontend` is root)
4. (Optional) Set Environment Variables:
   - `VITE_CONTRACT_ADDRESS`: `0x378640F3dbfC35F162945D12B73234138e211Bb6`
   - `VITE_GENLAYER_NETWORK`: `studioDevnet`
   *(Note: The dApp has built-in defaults pre-configured for your deployed contract on GenLayer Studio Next, so it works out-of-the-box even without setting env vars!)*
5. Click **Deploy**.

---

## Option 2: Deploying via Vercel CLI

If you have the Vercel CLI installed:

```bash
# 1. From repository root:
npx vercel

# Follow the interactive prompts:
# ? Set up and deploy “~/DracoLatch”? [Y/n] y
# ? Which scope do you want to deploy to? <Your Account>
# ? Link to existing project? [y/N] n
# ? What’s your project’s name? dracolatch
# ? In which directory is your code located? ./
```

To deploy directly to production:
```bash
npx vercel --prod
```

---

## Verified Configuration Summary

- **Live Studio Next Contract:** [`0x378640F3dbfC35F162945D12B73234138e211Bb6`](https://explorer-studio-next.genlayer.com/address/0x378640F3dbfC35F162945D12B73234138e211Bb6)
- **Explorer Base URL:** `https://explorer-studio-next.genlayer.com`
- **SPA Fallback Routing:** Enabled via `vercel.json` rewrites (`/(.*)` -> `/index.html`)
- **Node Support:** Node 18, 20, 22, 24+
