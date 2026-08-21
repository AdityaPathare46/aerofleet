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

## How the download buttons work

The buttons link to `downloads/AeroFleet-macOS.dmg` and `downloads/AeroFleet-Windows-Setup.exe` —
plain files served as part of this same Vercel deployment, not GitHub Releases. Deliberate choice:
this repo is private, and a private GitHub repo's release assets 404 for anyone without repo
access — the download button would only work for you, logged in, never for an actual visitor.
Vercel serves whatever's in this deployment publicly through its own URL regardless of whether the
source repo on GitHub is private, since Vercel only needs *build* access, which is separate from
public visibility. So the repo stays private and downloads still work for everyone.

`downloads/AeroFleet-macOS.dmg` is already committed. To add the Windows build once it's built at
college (`npm run tauri build` run **on Windows** — see `docs/COLLEGE_PC_TEST_RUNBOOK.md`):

```bash
cp path/to/AeroFleet_1.0.0_x64-setup.exe landing/downloads/AeroFleet-Windows-Setup.exe
git add landing/downloads/AeroFleet-Windows-Setup.exe
git commit -m "Add Windows installer to the landing page"
git push
```

Vercel redeploys automatically on push — the Windows button starts working within a minute or two
of that push, no dashboard steps needed.
