# DeckyShare v1.1.0 release checklist

## Verified automatically (CI / test harness)

- [x] Unit tests (Python backend: security, pairing code, uploads, integrity, updater, cancel, sender device)
- [x] Deck panel builds from `src/` and renders without errors (idle, transfer, stalled, cancel, every section open)
- [x] Phone page in a real browser: pick/remove files, Maximum Speed, Turbo, Fast, byte-identical results, stall warning, cancel, download, tabs
- [x] Cancel from the Deck for Maximum Speed, Turbo, Fast uploads and downloads (phone shows the cancel; no partial files left)
- [x] Computer pairing code: wrong code, single use, rate limit, expiry, real browser flow
- [x] Release ZIP passes the plugin's own updater validation; RC → 1.1.0 is offered as an update

## Check on a Steam Deck before publishing

- [ ] Update from the current RC through **More → Updates** installs v1.1.0
- [ ] Panel in Gaming Mode: controller can reach every button; address and code are on one line
- [ ] iPhone: QR → send 2 files → both arrive, Recent shows "From iPhone"
- [ ] Computer: address + code → send and download a file
- [ ] Cancel transfer on the Deck while the phone is sending
- [ ] 1 GB and 5 GB (ideally 10 GB) file, near the router, both directions; file opens fine afterwards
- [ ] Android browser: send and receive one file

## Publish

1. Actions → **Release on tag** → Run workflow → branch `v1.1.0-release`.
2. Check the release is **not** a pre-release and has `DeckyShare-v1.1.0.zip` and `DeckyShare.zip`.
3. Merge `v1.1.0-release` into `main` so the README and default branch show v1.1.0.
