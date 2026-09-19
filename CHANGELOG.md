# Changelog

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
