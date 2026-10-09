# Changelog

## v1.2.0-rc.1

- **Game clips**: a new "Game clips" section lists your Steam game recordings. Tap one and DeckyShare turns it into a regular MP4 (no re-encoding, same quality) and offers it on the phone page under **Get from Deck**. Works in Gaming Mode and for clips of any length (Steam itself only sends clips up to 59 seconds to a phone). A copy is kept in `Videos/Steam Clips`.

## v1.1.1

- The Deck panel now retries for up to ~30 seconds while Decky starts the backend after an install or update, instead of showing "Backend startup timed out" right away.

## v1.1.0

First stable release since v1.0.0. Everything from the 1.1.0 release candidates, summarised:

### Security
- Access now requires the session token from the QR code, or a one-time 6-digit code for computers (expires after 10 minutes, rate limited). v1.0.0 accepted anyone on the same network: please upgrade.
- Decky-only endpoints accept local requests only; uploads are verified and written to temporary files first.

### Connecting
- Phone: scan the QR code. Computer: open the short address (for example `192.168.8.131:8787`) and type the code shown on the Deck.

### Transfers
- Maximum Speed (single stream) plus resumable Turbo (3 parallel streams) and Fast modes, with pause, resume and cancel.
- Live speed and time left, and a "stalled" warning when no data arrives. Short phone pauses (up to 5 minutes) no longer kill a transfer.
- Cancel transfers from the Deck panel as well as from the phone/computer.
- Re-sending a file you deleted keeps its original name (no more "name (1)").
- Files received are listed with the sending device ("From iPhone", "From Mac", ...).

### Steam Deck panel
- Redesigned panel: transfer card at the top, QR + computer code, Send to phone, Received files, Recent, and a More group with Wi-Fi, Updates and Settings & support. New icon set and logo.
- Controller-friendly file manager: browse, copy, move, rename, new folder, move to trash.
- Wi-Fi check showing band, link speed, signal and power saving, with hints when Wi-Fi limits speed.
- Built-in updater that installs verified GitHub releases through Decky.

### Phone / computer page
- Redesigned page with Send to Deck / Get from Deck tabs, a file list you can edit, drag and drop on computers, and a large progress card.

### Project
- The Deck panel is built from source in CI; releases are built, tested and verified automatically.
- Optional self-hosted custom Decky store (`store/`).

## v1.1.0-rc.11.36

- Deck panel now follows the final mockup: header with "Ready · same Wi-Fi as your phone"; a Connect card with a large QR code, the computer address and code; a highlighted "Send to phone" button; "Received files" with a count; a "Recent" list; and a "More" group with Wi-Fi (band and signal), Updates ("Up to date" / "Update available") and Settings & support (notifications and support together).
- While a transfer runs, the panel shows the transfer card, the Wi-Fi summary and three buttons (Send to phone, Received files, Show QR code); the Connect card is tucked away until needed.
- New "Cancel transfer" button on the Deck (press twice to confirm). Works for Maximum Speed, Turbo and Fast uploads and for downloads; the phone shows "Cancelled on Steam Deck" instead of "Sent", partial files are removed, resumable retries of a cancelled upload are refused, and cancelling a download also stops sharing that file so the browser cannot resume it.

## v1.1.0-rc.11.35

- Redesigned Deck panel: flatter dark look matching the phone page, a new header with connection status, and sections in a clear order — transfer card, Connect, "Send to phone / PC", "Received files" (with a count badge), then a "More" group with Wi-Fi (shows band and signal at a glance), Notifications, Updates and Support.
- New icons: all emoji were replaced with one consistent set of line icons (sections, folders, file types), and a new DeckyShare logo in the header and the Decky sidebar.
- All features are unchanged: file browser and file manager, received files, Wi-Fi details, notifications, updates and controller navigation.

## v1.1.0-rc.11.34

- Deck panel: an active transfer now appears as a large card at the very top of the panel with the percentage, size, live speed and time left. A stalled transfer turns the card amber with a hint. The old "Live Transfers" section further down is gone.
- The Deck panel is now built from `src/index.tsx` in CI (release builds and release branches), instead of hand-maintained `dist` edits.

## v1.1.0-rc.11.33

- Redesigned phone/PC page: "Send to Deck" and "Get from Deck" tabs instead of one long scroll; a large file picker with a list of chosen files (remove any, drag and drop on a computer); a Maximum Speed switch; and a transfer card at the top with big progress, live speed, time left and a "no data" warning when the transfer stalls. Pause/Cancel only appear while sending, and the picker hides during a transfer.
- Get from Deck shows the file shared on the Deck with a badge on the tab, plus live progress for downloads.
- Fixed: re-sending a file you had deleted on the Deck saved it as "name (1).ext" until Decky restarted. Filename reservations now only cover the moment a file is being saved.
- The upload engine (Maximum Speed, Turbo, Fast, Reliable, pause, resume, cancel) is unchanged.

## v1.1.0-rc.11.32

- Connect a Mac or PC without a QR code: the Deck panel now shows a short address (for example `192.168.8.131:8787`) and a 6-digit code. Opening the address in any browser asks for the code, and the right code connects that browser.
- Codes expire after 10 minutes, work once, and are rate limited (6 wrong tries per device per minute; 30 wrong tries in total rotate the code).
- Phones keep connecting by scanning the QR code. The truncated tokenised URL and the Deck-only "Copy address" button were removed from the Connect card.

## v1.1.0-rc.11.31

- Adds a **Wi-Fi Check** section to the Deck panel showing the Deck's Wi-Fi band and channel, link send/receive rate, channel width, Wi-Fi standard, signal strength and power-saving state.
- Shows plain-language hints when the Deck link limits transfer speed (2.4 GHz, power saving on, weak signal, low link rate, narrow 5 GHz channel).
- Reads details with `iw` (falling back to `nmcli`) using a clean system environment; nothing is changed on the Deck.

## v1.1.0-rc.11.30

- Shows live transfer speed (last 3 seconds) instead of a since-start average, so a paused transfer reads 0 MB/s right away instead of slowly "decaying" (the 15 → 4 MB/s symptom). The average is still shown separately on the phone/PC page.
- Flags transfers that have received no data for 2+ seconds as "stalled" on both the Deck panel and the phone/PC page, with how long they have been stalled.
- Keeps a moving transfer alive through pauses of up to 5 minutes (was 30 seconds). Previously a short phone pause killed Maximum Speed uploads, which then restarted from zero. Idle keep-alive connections still close after 30 seconds.
- `tools/benchmark_transfer.py` now sends the session token (paste the full `?token=` URL or pass `--token`), so it works against RC11 builds.

## v1.1.0-rc.11.29

- Adds an optional, default-on Maximum Speed mode for browser-to-Deck transfers using one uninterrupted raw stream with no resume checkpoints, range lanes, or CRC work.
- Coalesces Deck-side progress updates so small mobile socket reads do not contend on shared transfer state for every packet.
- Keeps immediate cancellation, live progress, ETA, safe temporary-file writes, duplicate-name protection, and automatic partial cleanup.
- Keeps the existing resumable Turbo/Fast modes available by turning Maximum Speed off; Pause is intentionally unavailable while Maximum Speed is active.

## v1.1.0-rc.11.28

- Adds Turbo Mode for files of 64 MiB or larger, using three parallel native browser upload streams to utilize multiple HTTP connections.
- Writes the three non-overlapping ranges directly to their final offsets on Steam Deck, avoiding a second join/copy pass and extra full-file disk usage.
- Keeps per-lane Deck checkpoints for pause, reconnect, and retry while showing one combined transfer and progress value.
- Preserves the single-stream Fast Mode for smaller files and the CRC-verified Reliable Mode fallback.

## v1.1.0-rc.11.27

- Stops an older upload stream when the same device retries the same file, preventing background requests from splitting Wi-Fi bandwidth with the new attempt.
- Uses responsive socket reads for Fast Mode instead of waiting for a large receive buffer, improving steady mobile throughput and cancellation latency.
- Skips redundant server-side CRC work for native Fast Mode streams while retaining CRC verification in Reliable Mode.
- Fully resets the Send to Deck file picker, progress, diagnostic, and queue after cancellation.

## v1.1.0-rc.11.26

- Removes interrupted or abandoned upload requests from Live Transfers immediately, eliminating duplicate ghost entries.
- Starts a fresh speed timer from the saved Deck checkpoint when an interrupted upload resumes, fixing misleading low speed and ETA values.
- Keeps Fast Mode data resumable while separating the persistent upload session from the visible live request.

## v1.1.0-rc.11.25

- Adds a Blip-inspired Fast Mode for browser uploads: Safari, iPhone, Android, and desktop browsers now send one continuous native file stream instead of repeatedly reading and checksumming 4 MiB blocks in JavaScript.
- Keeps the partial file on Steam Deck when a fast upload is paused, interrupted, or backgrounded, then resumes from the Deck's confirmed byte offset.
- Makes Pause abort the active browser request immediately and resume from a stable receiver checkpoint; Cancel still removes the partial upload.
- Uses larger server reads for Fast Mode and exposes an authenticated upload-status endpoint for reliable recovery.

## v1.1.0-rc.11.24

- Reuse each iPhone/Safari file buffer for upload after worker CRC verification instead of reading the same chunk from the file provider twice.
- Keep the existing resumable 4 MiB transfer, checksum verification, pause/resume, and immediate cancellation behavior.

## v1.1.0-rc.11.23

- Show per-chunk Read, CRC, browser Upload, and server processing timings on the transfer page.
- Return server-side request timing with successful upload chunks for direct iPhone/Safari bottleneck diagnosis.

## v1.1.0-rc.11.22

- Keep HTTP/1.1 connections alive across sequential browser chunks instead of rebuilding TCP for every 4 MiB request.
- Add a bounded 30-second idle timeout and close error responses safely.
- Preserve the RC11.21 Safari worker/pipeline and exactly-once upload verification.

## v1.1.0-rc.11.21

- Move browser CRC32 calculation into a Web Worker when supported.
- Prepare the next 4 MiB chunk while the current chunk uploads, improving Safari/iPhone throughput without parallel server writes.
- Preserve bounded memory use, verified sequential offsets, pause/resume, retry, and immediate cancel behaviour.

## v1.1.0-rc.11.20

- Cancel now marks an active transfer cancelled without waiting for its upload lock.
- Added a server-side cancellation signal so blocked iPhone/Safari requests clean up safely when they release.
- Restored 4 MiB browser chunks after 16 MiB chunks proved inconsistent across Android and iPhone.

## v1.1.0-rc.11.19

- Increased browser upload chunks from 4 MiB to 16 MiB to reduce request overhead on large files.
- Increased backend streaming blocks and socket buffers for faster 5 GHz LAN transfers.
- Kept per-chunk CRC verification, resumable uploads, pause/resume and immediate cancellation intact.

## v1.1.0-rc.11.18

- Cancel now aborts the active browser upload request immediately instead of waiting for the current 4 MiB chunk.
- Server-side cleanup still removes the partial upload and marks the transfer cancelled.
- Cancelled uploads no longer enter the automatic connection-retry path.

## v1.1.0-rc.11.17

- Replaced partial socket writes with reliable `sendall` streaming.
- Added larger TCP send/receive buffers and buffered request reads.
- Increased backend upload/download streaming chunks from 1 MiB to 4 MiB.
- Removed the Android Share Sheet pairing section from the Deck panel while keeping already-paired Android clients compatible.

## v1.1.0-rc.11.16

- Added a dedicated responsive phone layout for the DeckyShare browser page.
- Mobile controls now use full-width touch targets, safe-area spacing and a single-column flow.
- Desktop browsers retain a wider two-column dashboard instead of receiving the phone layout.
- Improved long filename wrapping and upload-control alignment on narrow screens.

## v1.1.0-rc.11.15

- Android v0.2 moves Share Sheet uploads into a foreground data-sync service.
- The temporary Android share screen now closes immediately after enqueueing.
- Android notifications show live transfer progress, completion, and failures.
- Added Android 13 notification permission and Android 14 data-sync service declarations.

## v1.1.0-rc.11.14

- Added authenticated one-time pairing routes for phone Share Sheet clients.
- Added the Android Share Sheet pairing panel to the Decky plugin.
- Added the first native Android companion APK with single/multi-item share targets.
- Android uploads stream through a 1 MiB buffer instead of loading the full file into memory.

## v1.1.0-rc.11.13

- Removed external controller-focus glow, brightness boost, and scale animation.
- Replaced the focus effect with a thin border and small inset blue marker.
- Rebuilt the Browse Files toolbar as a compact always-visible two-row layout.
- Removed the large ellipsis menu and oversized Locations / Select controls.

## v1.1.0-rc.11.12

- Reduced the controller focus outline, brightness, scale, and glow intensity.
- Kept a clear blue focus indicator without the oversized luminous bar effect.

## v1.1.0-rc.11.11

- Fixed update discovery when GitHub returns prereleases out of semantic-version order.
- The updater now evaluates the complete release page and selects the highest compatible version.

## v1.1.0-rc.11.10

- Added controller-friendly open/close accordions to every section except Connect phone / PC.
- Kept Browse Files open by default and auto-opens Live Transfers when a transfer begins.
- Made the Locations, Select, and New folder controls compact.
- Replaced the empty breadcrumb control with a readable current-folder path.
- Removed overlapping native/custom focus rings so only one item is highlighted.

## v1.1.0-rc.11.9

- Replaced direct plugin-folder updates with Decky Loader's native installer handoff.
- Prevented permission-denied failures caused by a running plugin trying to rename itself.
- Preserved the RC11.8 high-visibility controller focus treatment.

## v1.1.0-rc.11.8

- Added a high-contrast blue controller-focus outline and glow to every action.
- Added visible focus feedback for search, rename, and new-folder text fields.
- Preserved touch input and Decky's native focus ring.

## v1.1.0-rc.11.7

- Restored the bundled HTTP compatibility layer required by Decky Loader's frozen Python runtime.
- Removed a blocking hostname lookup from backend startup.
- Made LAN server startup idempotent, thread-safe, and time-bounded.
- Preserved RC11.6 authenticated LAN sessions and controller navigation.

## v1.1.0-rc.11.6

### Added
- Native Steam Deck controller navigation using Decky UI controls
- D-pad/left-stick focus movement and A-button activation
- B-button cancellation and one-level folder navigation
- One-press visible Back button in Browse Files
- Automatic focus on the first visible file or folder

### Changed
- B returns to Locations when already at a quick-location root
- Browse Files keeps RC11.4 compact rows and RC11.2 paging/sort protections
- Repository now contains reproducible frontend source and Rollup configuration for Store builds

### Security
- Require a cryptographically random session token for every LAN browser request
- Exchange the QR/address token for an HttpOnly, SameSite=Strict session cookie
- Restrict legacy plugin bootstrap/status HTTP endpoints to the Steam Deck loopback interface

## v1.1.0-rc.1

Release candidate focused on transfer reliability and a cleaner Deck/browser experience.

### Added
- Multi-file upload queue with per-file status
- Pause, resume and cancel controls for browser-to-Deck uploads
- Automatic retry and resumable 4 MiB upload chunks
- CRC32 verification for each uploaded chunk
- Exactly-once upload IDs to prevent duplicate final saves when a success response is lost
- Isolated upload sessions for simultaneous files with the same filename
- Zero-byte upload and download handling
- Duplicate filename protection
- Cleaner storage-full (`507`) and write-failure (`500`) responses
- Stale partial-upload cleanup after plugin restarts
- Real-device upload/download benchmark tool
- Refreshed Decky panel and responsive phone/PC browser interface
- Connection status, copy-address action and improved received-file controls
- Notification deduplication and clearer transfer progress states

### Reliability notes
- Exactly-once replay tracking is currently in memory; a plugin/server restart does not preserve completed-upload replay records.
- Recent partial files are preserved across restarts so the server can report their current offset when the same upload ID reconnects; stale partials older than 24 hours are cleaned up.
- Upload integrity uses CRC32 per chunk. It is intended for accidental transfer corruption detection, not cryptographic authentication.
- Large-file performance claims are intentionally withheld until real Steam Deck hardware tests are completed.

### RC validation still required
- SteamOS Stable test
- SteamOS Beta test
- 1 GiB upload/download benchmark
- 10 GiB upload/download benchmark
- 50 GiB upload/download benchmark
- Restart during an active upload and verify resume behavior
- Lost final-response replay test on real hardware

## v1.0.0

First public release of DeckyShare.

### Features
- Two-way wireless file transfer between Steam Deck and phone/PC
- Gaming Mode file browser
- QR-code and local-network connection
- Large-file download resume using HTTP Range
- Chunked/resumable uploads
- Live progress, speed and ETA
- Received-files list and delete action
- Matching Deck and browser UI
- Buy Me a Coffee support link

### Notes
- Both devices must be reachable on the same local network.
- Received files are currently stored in `~/Downloads/DeckShare/`.
