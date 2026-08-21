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

## Unsigned build — expect an OS warning on first launch

Neither installer is code-signed (that needs a paid Apple Developer ID Program membership — $99/yr
— and, separately, a Windows code-signing certificate; neither is set up, and enrolling is a real
account/cost decision only the repo owner can make). Concretely, this means:

- **macOS**: a browser download gets Gatekeeper's quarantine flag, and an ad-hoc-signed
  (not Developer-ID-signed, not notarized) app downloaded with that flag gets flatly rejected —
  confirmed directly with `spctl -a -vv` against the built app, not just macOS's own wording, which
  unhelpfully says "AeroFleet is damaged and should be moved to the Trash." It isn't damaged.
  One-time fix per machine: `xattr -cr /Applications/AeroFleet.app` in Terminal, then open normally.
- **Windows**: SmartScreen shows "Windows protected your PC" for the same unsigned-build reason —
  milder than Gatekeeper, doesn't require Terminal. Click **More info** → **Run anyway**.

Both are now called out directly on the landing page, right under the download buttons, so a
visitor doesn't hit a dead end. The only way to remove the warning entirely (not just explain it)
is actual code signing + notarization — worth doing before wider distribution, not required for a
college demo.
