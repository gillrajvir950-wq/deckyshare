# DeckyShare public Shortcut build blueprint

This document is the human-readable source of truth for the iCloud Shortcut that ships alongside DeckyShare.

The shortcut is named **DeckyShare**, is enabled in the iOS Share Sheet, and accepts Files, Images, Media, URLs and Text.

On first run it pairs to DeckyShare using the temporary pairing code shown by the Steam Deck plugin. After a successful pairing it stores the returned authenticated upload endpoint for later Share Sheet runs. On later runs it posts every shared item to that saved endpoint and shows a success notification only after a successful response.

The final iCloud URL must be created from Apple's Shortcuts app with **Share → Copy iCloud Link**. The plugin/repository cannot mint that Apple-hosted link itself.
