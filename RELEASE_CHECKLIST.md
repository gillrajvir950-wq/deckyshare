# DeckyShare v1.1.0 RC1 validation

Do not promote RC1 to stable until the required hardware checks below are complete.

## Startup and UI
- [x] Backend starts on Steam Deck with split RC1 modules
- [x] Copy address works in Decky panel
- [x] Copy path works in Decky panel
- [ ] Show folder opens the received file's directory
- [ ] All Decky panel buttons checked once end-to-end
- [ ] Phone/PC UI checked on mobile and desktop browser

## Transfers
- [ ] Small file: phone/PC -> Deck
- [ ] Small file: Deck -> phone/PC
- [ ] 1 GiB upload and download
- [ ] 10 GiB upload and download
- [ ] 50 GiB upload and download
- [ ] Multiple-file queue
- [ ] Pause / Resume / Cancel
- [ ] Same-name concurrent uploads produce distinct files
- [ ] Zero-byte upload and download

## Interruption and recovery
- [ ] Wi-Fi disconnect/reconnect during upload
- [ ] Backend restart during upload with same upload ID
- [ ] Lost final upload response/retry does not duplicate within same backend session
- [ ] Deck -> phone/PC interrupted download can resume using HTTP Range where the client supports resume
- [ ] Phone screen-off/background behavior documented and tested on available mobile browser

Note: mobile operating systems may suspend a browser download when the screen turns off. DeckyShare can support byte-range requests on the server, but cannot guarantee that every mobile browser will automatically resume a suspended native download.

## Storage and integrity
- [ ] CRC32 mismatch retry behavior
- [ ] Disk-full / quota error reports cleanly
- [ ] Cancelled upload cleans partial data
- [ ] Stale partial cleanup (>24h)

## SteamOS
- [ ] SteamOS Stable
- [ ] SteamOS Beta

## Release gate
- [ ] No known data-loss/overwrite bug
- [ ] No reproducible backend startup regression
- [ ] Changelog/release notes updated with verified behavior only
- [ ] Build packaged and ZIP integrity checked
