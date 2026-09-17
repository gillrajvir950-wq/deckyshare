# DeckyShare iPhone Shortcut onboarding

DeckyShare's public iPhone Shortcut is designed to be installed once from an iCloud Shortcut link and then paired to a Steam Deck on first run.

## User flow

1. Install the public **DeckyShare** Shortcut from the release/README link.
2. Open DeckyShare on Steam Deck and choose **iPhone Shortcut → Start pairing**.
3. The Deck shows a LAN address and a temporary six-digit code. No QR code is used.
4. Run the Shortcut once. It asks for the Deck address and six-digit code.
5. The Shortcut POSTs to `/shortcut/pair`, receives the authenticated `/shortcut/share` endpoint, and saves that endpoint locally for future runs.
6. After pairing, Photos / Files / Safari → Share → DeckyShare sends directly to the paired Deck.

## Security model

- Pairing code is random, one-time and expires after 10 minutes.
- Failed pairing attempts are rate-limited per source address.
- Successful pairing returns the existing persistent DeckyShare Share Sheet key; the key is never displayed in the Deck UI.
- The existing Share Sheet upload endpoint continues to require that key.

## Shortcut blueprint

The public Shortcut should:

- Receive Files, Images, Media, URLs and Text from the Share Sheet.
- On first run, ask for the Deck address shown by DeckyShare, e.g. `192.168.1.42:8787`.
- Ask for the six-digit pairing code.
- POST to `http://<deck-address>/shortcut/pair?code=<code>`.
- Read the returned JSON field `endpoint` and save it as the Shortcut's local DeckyShare configuration.
- On later Share Sheet runs, load the saved endpoint and POST each shared item to it.
- If the saved endpoint is unreachable, offer to pair again rather than silently failing.
- Show `Sent to DeckyShare` only after a successful HTTP response.

## iCloud link publication

Apple creates the public iCloud Shortcut link from the Shortcuts app itself. Once the generic Shortcut above is built on an iPhone/iPad/Mac, use **Share → Copy iCloud Link** and place that link in the DeckyShare README/release notes.
