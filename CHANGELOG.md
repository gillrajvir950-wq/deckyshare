# Changelog

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
