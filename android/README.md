# DeckyShare Android Share Target

This companion app registers `DeckyShare` for Android `ACTION_SEND` and
`ACTION_SEND_MULTIPLE`. It streams shared files to the authenticated
`/shortcut/share` endpoint without copying the whole file into memory.

## Pairing

1. In the DeckyShare plugin, open **Android Share Sheet** and choose **Start pairing**.
2. Open the Android app and enter the displayed Deck address and six-digit code.
3. After pairing, use Photos or Files → Share → DeckyShare.

The phone and Steam Deck must be on the same local network. The authenticated
endpoint is stored in Android private app preferences.

Shared items are handed to a foreground data-sync service. The temporary share
screen closes immediately, while an Android notification shows transfer
progress and the final result.

## Build

Open this `android/` directory in Android Studio and build the `app` module.
