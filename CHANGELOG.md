# Changelog

## 0.3.4

- When the startup check finds a newer version, the app now asks whether to download it and restart. Nothing installs unless you choose it; "Later" asks again the next time the app starts.

## 0.3.3

- The Windows EXE is now built with Python 3.14, which still receives Windows security updates. It was built with Python 3.12.
- The About / Support panel and the feedback form no longer open taller or wider than the screen.
- The app now checks GitHub for a newer version at startup by default. Untick "Check GitHub for updates at startup" under Updates to turn it off. If you had already changed that checkbox, your choice is kept.

## 0.3.2

- The Feedback / Support button moved into the title bar, where the vine border no longer covers it. It reads "Update available" when a check finds a release.
- The About / Support panel and the feedback form now share the main window's look: wood title bar, burl panel, vine border and parchment fields.
- The panel shows the update status beside the version. "Check for updates" becomes "Download" when a release is found and "Cancel" while it downloads.
- Support buttons carry their platform logos. Unavailable buttons now look disabled.
- Fixed clicks on a support dialog being taken as a resize of the main window where the two overlap.
- Message boxes now use the dark wood background, so their amber text is readable.

## 0.3.1

- Refreshed the Feedback / Support panel: Discord, Reddit, GitHub, LinkedIn and AdamCh.com buttons, "Check for updates" and "Feedback form" side by side, and updated support wording and links.
- The main window button is now labelled Feedback / Support.

## 0.3.0

- Added a prominent Feedback / Donate button with the FrodoTappins support panel, Discord invite and donation options.
- Added a feedback form that identifies FrodoTappins and its version, remembers contact details locally, and keeps the message when delivery fails.
- Added optional startup update checks, manual GitHub release checks, and verified download, install and restart with rollback protection. Existing counts and settings are preserved.
- Changed cloud sync to cumulative installation totals with seven days of comparison snapshots. Daily history remains local.
- Book progress now uses combined cloud totals when cloud sync is configured, including previous installations and other devices. Installation IDs remain separate, and unreadable local data is preserved.
