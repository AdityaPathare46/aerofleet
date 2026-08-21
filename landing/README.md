# AeroFleet Landing Page

A static, no-build-step site (`index.html` + `style.css` + `script.js`) — nothing to install,
nothing to compile. Same design tokens as the desktop app (navy accent sampled from the logo,
Space Grotesk + JetBrains Mono).

## Deploying to Vercel

This lives in a subdirectory of the main repo, so when connecting the GitHub repo in Vercel:

1. [vercel.com/new](https://vercel.com/new) → Import `AdityaPathare46/aerofleet`.
2. Under **Root Directory**, click Edit and set it to `landing`.
3. Framework Preset: **Other** (it's plain static HTML — no build command needed).
4. Deploy.

Or from the CLI, from inside this directory:

```bash
npm install -g vercel   # one-time
cd landing
vercel --prod
```

Either way, Vercel needs your own account/login — this is a one-time step only you can do (a
browser-based Vercel login), not something that can be scripted on your behalf.

## Before the download buttons actually work

The buttons link to `https://github.com/AdityaPathare46/aerofleet/releases/latest/download/<file>`
— GitHub's stable "always get the newest release's asset with this exact filename" URL pattern.
Nothing resolves there until a Release actually exists with matching asset names:

1. On GitHub → **Releases** → **Draft a new release** (tag e.g. `v1.0.0`).
2. Attach the macOS installer, renamed exactly to **`AeroFleet-macOS.dmg`**
   (already built — `AeroFleet_1.0.0_aarch64.dmg`, delivered separately; just rename on upload).
3. Once the Windows installer is built (`npm run tauri build` run **on Windows**, see
   `docs/COLLEGE_PC_TEST_RUNBOOK.md`), attach it too, renamed to **`AeroFleet-Windows-Setup.exe`**.
4. Publish the release. Both landing-page buttons resolve immediately — no code change needed,
   since the URL pattern always points at whatever the latest release's matching filename is.
