# FrodoTappins - There and Backspace Again

So. I was idly wondering how often I type the equivalent of the Lord Of The Rings trilogy. 
Then I excercised free will. 

A small, privacy-respecting activity keystroke counter for Windows, that can sync across devices via a free cloudflare account. 

<img width="1200" height="627" alt="frodotappins-linkedin-v2" src="https://github.com/user-attachments/assets/0729daeb-1542-4f45-92cd-a68efa713bb3" />
<p align="center">
And a larger preview. </p>

<p align="center">
<img width="571" height="1035" alt="frodotappins" src="https://github.com/user-attachments/assets/b978ce63-2f48-497e-aa79-ec9cb6508a4c" />
</p>
<p align="center">
<em>Day is ended, dim my eyes,<br>
but journey long before me lies.</em>
</p>

It tracks, per day:

- **Keystrokes** — total key presses
- **Words** — counted by detecting word boundaries
- **Deletions** — Backspace and Delete presses (also counted as keystrokes)
- **Alt-Tabs** — Alt+Tab window switches
- **Power cycles** — restarts / shutdowns, detected from the OS boot time

It also shows, against your all-time word total, how far you've typed toward
some of Tolkien's works (*The Hobbit*, *The Lord of the Rings*, *The
Silmarillion*) — a percentage and the words you have left to go for each.

It can run entire offline, or sync multiple devices via a free-tier Cloudflare
account's DB + workers (setup instructions included). 

Why? Idle curiousity. Open source so you can verify keystrokes are not logged,
stored, or transmitted. Only counted.

It is fully **portable and offline**: everything lives in the app's own folder
(move it, copy it to a USB stick, or delete it to uninstall — see below), and it
makes no network connections unless you set up cloud sync, use the optional GitHub update checks or send feedback. It runs in
the system tray and can start at login. With cloud sync configured it **auto-syncs
every 15 minutes** (and on demand), showing each device's total and the combined
cloud total side by side, so several machines roll into the same figures.

### Privacy: it counts, it does not log

This is a *counter*, not a keylogger. On each key press it increments a number
and, to count words, it checks whether the key was a letter/digit or a
separator — then discards that. **The actual character is never stored, written
to disk, or transmitted.** Only cumulative counts (and your installation ID/name) leave your
machine, and only when it syncs to a cloud you've set up yourself. No window
titles, no clipboard, no key content. The source is short on purpose so you can
verify this yourself (see `Counter._on_press` in `tracker.py`).

---

## Easy install 

There is a ZIP file in the latest release (top right of the github page). 

Download that zip, extract to your preferred directory, and run the exe. That's it. 
The other files are only needed if you're setting up the cloud sync. The exe will
create files to store data in the same folder. Just delete the whole schemozzle 
to uninstall. 

---

## Files

```
tracker.py          The local app (listener + GUI + tray + sync + autostart)
cloud_sync.py       Cumulative sync protocol and cloud-total validation
updater.py          GitHub release checks and portable EXE updates
requirements.txt    Python dependencies
build.bat           One-command build -> dist/FrodoTappins.exe
worker.js           Cloudflare Worker (the sync API)
schema.sql          D1 cumulative totals and seven-day snapshot tables
migrate-v2.sql      Additive backfill for an existing daily-history database
wrangler.toml       Optional — only used if you deploy via the Wrangler CLI
```

---

## 1. Build youself method. (Windows, *.exe)

You need [Python 3.9+](https://www.python.org/downloads/) installed (tick *Add
Python to PATH* in the installer). Then, in this folder:

```
build.bat
```

That installs the dependencies + PyInstaller and produces **`dist\FrodoTappins.exe`**
— a single portable file with no console window. Double-click it and a small
window appears showing today's figures and your all-time totals.

> Prefer to just run it without building? `pip install -r requirements.txt`
> then `python tracker.py`.

### Updating the portable app

The **Updates** section shows the installed version. Choose **Check GitHub**
to look for a newer stable release. **Check GitHub for updates at startup**
is optional and starts disabled, so offline use remains available.

When a compatible release is found, **Download and restart** downloads it,
checks its size and SHA-256 against GitHub's release metadata, saves your counts,
replaces the EXE and restarts the app. You can cancel before installation.
The controls use the same wood and parchment styling as the rest of the app.

Updates replace only the EXE. Keep using the same app folder: `data.json`,
`config.json`, your device ID, counts and cloud settings stay in place. An older
EXE is kept as `previous.exe` inside an adjacent `.FrodoTappins-update-*` folder.
If replacement or launch fails, the helper attempts to restore that backup.
Successful launch is not a guarantee that a new version has no bugs; keep the
backup until you are happy with the update.

In-app installation requires the packaged Windows EXE and a writable folder.
A release without a verifiable standalone `FrodoTappins.exe` is offered through
**Releases** for manual download instead. Older releases without the updater
need one manual upgrade: close the old app and replace its EXE in the existing
folder, preserving both JSON files.

GitHub checks send no counts, device IDs or cloud credentials. They do make
ordinary HTTPS requests to GitHub. The checksum verifies the download against
GitHub metadata; it is not an independent publisher signature.

For release packages, attach the `dist/FrodoTappins.exe` produced by `build.bat`
as a standalone GitHub release asset named `FrodoTappins.exe`, alongside the ZIP.
Set `VERSION` in `updater.py` to the corresponding stable tag version before
building. Drafts, prereleases, equal and older versions are not offered.

### Where your data lives (portable)

FrodoTappins keeps everything in **its own folder**, right next to the executable:
`data.json` (your counts, device id, start date) and `config.json` (your Worker
URL + key, and the auto-sync setting). Nothing is written to AppData or the
registry. To move it, move the whole folder; to back it up, copy the folder; to
**uninstall, just delete the folder.** The window shows the exact location and
has an **Open folder** button. The folder must be somewhere writable — a normal
folder, Desktop, or USB drive, not `Program Files` — or the app warns you on start.

### Start at login

Tick **"Start at login"** in the window. That drops a shortcut (pointing at the
exe, with `--minimized` so it starts hidden in the tray) into your Startup folder
— no registry changes, no admin rights. Because the shortcut stores the exe's
current path, **moving the folder breaks auto-start**; just re-tick the box to
repoint it. Untick to remove.

### A note on antivirus

Any program that hooks the keyboard *and* is packed into a one-file exe can trip
heuristic antivirus flags — this is common for legitimate tools too (AutoHotkey,
WhatPulse, etc.). Since you built it yourself from source you can verify it's
benign and add a Defender exclusion if needed. 

---

## 2. Cloud sync with Cloudflare (free tier) — optional

The app works fully standalone; this part just adds the cross-device totals. You
set up one Worker backed by one D1 database **entirely in the Cloudflare web
dashboard — no Wrangler, no command-line tools, nothing to install.** All you
need is a free Cloudflare account and a browser. (If you'd rather use the
Wrangler CLI, see the note at the end of this section; you can ignore
`wrangler.toml` otherwise.)

Two names must match the code exactly (both case-sensitive): the database binding
**`DB`** and the secret **`API_KEY`** — these are what `worker.js` reads via
`env.DB` and `env.API_KEY`.

**a. Create the database and load the table**

1. Dashboard → **Storage & Databases → D1 SQL Database → Create Database**. Name
   it (e.g. `frodotappins`) and create it.
2. Open the database console and execute the statements in `schema.sql`.
   This creates `device_totals`, `device_snapshots` and the snapshot-date index.
   For an existing installation with a `stats` table, follow the upgrade steps
   below before replacing its Worker.

**b. Create the Worker**

3. **Workers & Pages → Create application → Create Worker**, name it (e.g.
   `frodotappins-sync`), and **Deploy** (this deploys a placeholder you'll replace).

**c. Bind the database**

4. Open the Worker → **Bindings → Add binding → D1 database**. Set the variable
   name to **`DB`** and select your database.

**d. Add the API key**

5. Worker → **Settings → Variables and Secrets → Add**. Choose type **Secret**,
   name **`API_KEY`**, value = any long random string you choose. **Deploy.** Keep
   a copy — the value is hidden once saved, and it's the same key you put in the
   app. Treat it like a password.

**e. Paste the code**

6. Worker → **Edit code** (`</>`), clear the file, paste the full contents of
   `worker.js`, and **Deploy**. Make sure the workers.dev URL is enabled
   (Settings → Domains & Routes). The Worker's page shows its
   `https://<worker-name>.<your-subdomain>.workers.dev` URL.

**Connect the app:** in FrodoTappins's *Cloud* box paste that Worker URL and the same
API key, click **Save**, then **Push to Cloud**. Sanity-check in a browser by
visiting `<your worker URL>/totals` — it should return `{"error":"unauthorized"}`
(the Worker is alive; a browser doesn't send the key). Install the app on another
PC, point it at the same URL + key (it appears as its own device), and both
machines tally into the combined total.

> **Recreating or renaming the Worker?** The `DB` binding and `API_KEY` secret are
> per-Worker and don't carry over — re-add both (each followed by a Deploy) on the
> new Worker. A missing `DB` binding shows up as HTTP 503 on sync; a wrong/missing
> key shows up as 401; a request blocked by Cloudflare's edge shows up as 403.

> Prefer the command line? `wrangler.toml` is there for the Wrangler CLI
> route, but the dashboard steps above don't need it.

---

## How the numbers work

- **Two storage tiers, kept locally.** Every event increments two independent
  counters: a per-**minute** bucket and a per-**day** bucket. The minute tier is
  kept for ~26 hours (older buckets are pruned); the day tier is kept forever.
  This keeps the file small while making every window cheap to compute.
- **The breakdown** sums whichever tier fits the window:
  - *Last hour* / *Last day* come from the minute tier — true rolling windows
    (the trailing 60 minutes / 24 hours), accurate to the minute.
  - *Last week* / *Last month* / *Last year* / *All-time* come from the day tier
    (the last 7 / 30 / 365 day-buckets, and every bucket respectively),
    accurate to the day.
- **Start date / days since.** The first run records a start timestamp; "days
  since" is calendar days from that date. Existing installs inherit their
  earliest recorded day as the start date when you upgrade.
- **Cumulative cloud totals.** Each installation uploads one all-time total for
  each counter, regardless of how long it has been running. The server checks
  its revision and refuses stale or decreasing totals. Repeating a sync does
  not add the same counts twice. A device offline for more than seven days can
  still upload its complete cumulative total when it returns.
- **Seven-day comparison history.** The cloud keeps the last accepted cumulative
  snapshot for each installation on each UTC date, for today and six preceding
  dates. Older snapshots are pruned on the next accepted sync; an idle database
  retains them until then. Lifetime totals are never pruned. These snapshots
  support manual comparison/recovery; they are not daily activity buckets or a
  full database backup. Local daily history remains intact.
- **Installation identity.** Keep `data.json` when updating or moving an existing
  installation. Start a separate machine without copying that file so it gets
  its own ID. Identical computer names do not imply duplicate counts; the cloud
  shows an ID suffix for matching names. Unreadable saved data stops startup
  instead of silently creating a new identity. Conflicting histories require
  reconciliation; the app will not silently overwrite a larger cloud total.
- **Power cycles** are detected by comparing the current OS boot time against the
  last one seen. Relaunching the app within one session does not count; only a
  real restart does. The first run records the boot time without counting it.
- **Deletions** count every Backspace and Delete press. They are *also* counted
  as keystrokes (every physical press is one keystroke), so the deletions column
  is a subset of the keys column, not a separate total.
- **Words vs. Tolkien** compares the last fetched **combined cloud all-time**
  word total when cloud sync is configured, or your local all-time total when
  used offline, against fixed,
  widely-cited word counts for *The Hobbit*, the three *Lord of the Rings*
  volumes (and their aggregate), and *The Silmarillion*. For each it shows the
  book's total, the percentage you've typed, and the words you have left to go;
  a finished work turns green. It's a bit of fun, not a literary measurement —
  "words" here are typing-detected word boundaries, not published wordcount
  methodology. The trilogy uses 455,125 words (177,227 + 143,436 + 134,462),
  so finishing one volume does not mean finishing the trilogy. The panel shows
  its source and last cloud refresh. Before the first fetch it shows Pending;
  after a failed fetch it retains the last good cached total. Devices agree
  when they have fetched the same cloud snapshot; unsynced typing is reflected
  after the next push and refresh.

### Upgrading an existing cloud database

Back up the database and each app folder first. Apply `schema.sql`, then
`migrate-v2.sql` to backfill cumulative totals from the existing `stats` table.
Verify per-installation and combined sums before deploying the new `worker.js`.
After the previous Worker requests have finished, rerun the additive backfill
and verify again to capture any final legacy writes. Keep the original `stats`
table as an archive during the upgrade; the new Worker no longer modifies it.
Do not group or delete installations by computer name.

Upgrade the Worker before the apps. New apps refuse to upload to the old
protocol. Existing apps can upload full history to the new Worker during the
transition. Rolling back the Worker after new syncs requires reconciling the
new cumulative data; the retained legacy table alone is then out of date.

### API reference (for building your own dashboard)

Both endpoints need `X-API-Key: <your key>`.

- `GET /totals` → `{ "protocol": 2, "global": {...}, "device_count": N, "devices": [...] }`.
  Each device includes its five cumulative counters and `revision`.
- `POST /sync` accepts `protocol: 2`, `device_id`, `device_name`, `totals` (all
  five nonnegative integer counters), and `expected_revision` from `/totals`
  (zero for a new installation). Success returns `ok: true`, `protocol: 2`
  and the new `revision`. HTTP 409 means stale or decreasing history: refresh
  and reconcile before retrying. Counts must fit a JavaScript safe integer.
- Older apps may still send their complete `days` array. The Worker collapses
  it into cumulative totals and applies the same nondecreasing checks. Their
  book display remains local until the app is upgraded.

CORS is open, but a public browser dashboard would expose your key in client
code — keep the key private and query `/totals` from somewhere trusted (or add a
separate read-only endpoint if you want a public view).

---

## Limitations / notes

- **After upgrading, the rolling windows start fresh.** The minute tier can't be
  reconstructed from old data, so *Last hour* / *Last day* fill in as you use the
  app. *Last week / month / year / all-time* draw on the day tier, so your
  existing history counts immediately.
- **The cloud figures are all-time**, per device and combined. The Cloud panel
  shows each device's running total and a combined total row; the per-window
  breakdown (hour/day/week/...) stays a local, this-device view, since rolling
  windows across devices would need fine-grained synced data and server-side
  windowing (a deliberate scope choice — the Worker just keeps the totals).
- **Words are approximate.** A word is counted when a letter/digit run is
  followed by a separator, which matches normal typing well but won't reflect
  IME / CJK composition precisely.
- **Auto-sync runs every 15 minutes** whenever a Worker URL and key are set, and
  only then — cloud sync makes no network calls without cloud configuration. GitHub update checks are separate and optional.
  Use the "Auto-sync to cloud every 15 min" checkbox to turn it off; "Push to
  Cloud" (push + pull) and "Refresh total" (pull only) remain for on-demand use.
- Built and tested against the structure of `pynput`/`psutil`/`PySide6` (the Qt
  GUI). The `build.bat` excludes the heavy Qt modules the app never uses to keep
  the single-file exe small; if PyInstaller misses something on your machine,
  adjust the `--exclude-module` / add `--hidden-import` flags there.
- Windows-oriented as written (Startup-folder shortcut via PowerShell,
  `os.startfile`). The counting core (`pynput`) and the Qt GUI/tray are
  cross-platform; only the autostart shortcut is Windows-specific.


## Feedback and support

<p align="center">
  <a href="https://discord.gg/fs4WyaQPA"><img src="assets/support/social-discord.svg" width="38" height="38" alt="Discord" title="Discord"></a>
  <a href="https://www.reddit.com/r/AdamChsLab/"><img src="assets/support/social-reddit.svg" width="38" height="38" alt="Reddit" title="Reddit"></a>
  <a href="https://github.com/AdamChesters"><img src="assets/support/social-github.svg" width="38" height="38" alt="GitHub" title="GitHub"></a>
  <a href="https://www.linkedin.com/in/adamchesters/"><img src="assets/support/social-linkedin.svg" width="38" height="38" alt="LinkedIn" title="LinkedIn"></a>
  <a href="https://adamch.com"><img src="assets/support/social-website.svg" width="38" height="38" alt="AdamCh.com" title="AdamCh.com"></a>
</p>

<p align="center">Thanks for using FrodoTappins. I like to fix bugs and implement features rapidly. Issue? Idea? Let's work on it! Contact me anywhere you prefer.</p>

<h3 align="center">Support</h3>

<p align="center">I love making things to have fun, share fun, and make life a lil better. If you got value out of one of them, feel free to buy us a coffee. Or a house. Push comes to shove, I prefer Aston Martin. Supporters get golden crowns on the Discord / tags on the subreddit!</p>

<p align="center">
  <a href="https://github.com/sponsors/AdamChesters"><img src="assets/support/support-github.svg" width="220" height="86" alt="GitHub Sponsors" title="GitHub Sponsors"></a>
  <a href="https://buymeacoffee.com/adamch"><img src="assets/support/support-buymeacoffee.svg" width="220" height="86" alt="Buy Me a Coffee" title="Buy Me a Coffee"></a>
  <a href="https://www.paypal.com/donate/?business=KLHSZPXTSVSAU&amp;no_recurring=0&amp;item_name=I%27ve+donated+to+lots+of+small+creators+for+their+useful+little+tools%2C+now+I+create+them.+Dig+one?+I%27d+love+your+support.&amp;currency_code=AUD"><img src="assets/support/support-paypal.svg" width="220" height="86" alt="Support with PayPal" title="Support with PayPal"></a>
</p>
