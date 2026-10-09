# DeckyShare custom store

Decky Loader can install plugins from a custom store instead of the official
one. This folder holds a tiny Cloudflare Worker that serves such a store for
DeckyShare, built live from this repository's GitHub Releases.

Why a Worker: Decky requests the store with an `X-Decky-Version` header. That
triggers a browser CORS preflight which GitHub (raw files and Pages) refuses,
so a JSON file hosted on GitHub shows up as an empty store. The Worker answers
the preflight and returns the list in Decky's format.

| URL | Lists |
| --- | --- |
| `https://<your-worker>/plugins` | stable releases only |
| `https://<your-worker>/rc/plugins` | stable + release candidates |

Each version points at the release ZIP (`artifact`) with its SHA-256 (`hash`)
taken from GitHub, and Decky verifies that hash before installing. New
releases appear within about 5 minutes; nothing needs updating per release.

## Deploy (once, free plan is enough)

1. Create a free account at <https://dash.cloudflare.com/sign-up>.
2. Go to **Workers & Pages** → **Create** → **Create Worker**, name it
   `deckyshare-store`, and click **Deploy**.
3. Click **Edit code**, replace everything with the contents of
   [`worker.js`](worker.js), and click **Deploy**.
4. Open `https://deckyshare-store.<your-subdomain>.workers.dev/rc/plugins` in a
   browser. You should see JSON with `"name": "DeckyShare"`.

Optional: add a `GITHUB_TOKEN` secret (read-only, public repo access) under
the Worker's **Settings → Variables** to avoid GitHub's anonymous rate limit.
Responses are cached for 5 minutes, so this is rarely needed.

Using the CLI instead: `npx wrangler deploy` from this folder (see
[`wrangler.toml`](wrangler.toml)).

## Use it on the Steam Deck

1. Open Decky (Quick Access → plug icon) → **Settings** (gear).
2. Set **Store channel** to **Custom** and enter the store URL, e.g.
   `https://deckyshare-store.<your-subdomain>.workers.dev/rc/plugins`.
3. Open the Decky store: DeckyShare appears with an **Install** button.

While Custom is selected, Decky shows only this store. Switch the channel back
to **Default** to browse the official store again; installed plugins stay.
