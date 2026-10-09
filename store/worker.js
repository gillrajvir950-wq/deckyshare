// DeckyShare custom Decky store — Cloudflare Worker.
//
// Decky Loader can use a custom store (Decky settings > Store channel: Custom).
// It fetches the store URL with an "X-Decky-Version" header, which forces a
// CORS preflight that GitHub-hosted files refuse. This Worker answers that
// preflight and serves the store list built live from GitHub Releases, so a
// new release appears in the store without any extra step.
//
//   https://<worker>/plugins       stable releases only
//   https://<worker>/rc/plugins    stable + release candidates (pre-releases)
//
// Each version points Decky straight at the release ZIP ("artifact") and gives
// the ZIP's SHA-256 ("hash"), which Decky checks before installing.

const REPO = "gillrajvir950-wq/deckyshare";
const PLUGIN_NAME = "DeckyShare";
const ASSET_RE = /^DeckyShare-v.+\.zip$/i;
const CACHE_SECONDS = 300;

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "X-Decky-Version, Content-Type",
  "Access-Control-Max-Age": "86400",
};

export function releasesToStore(releases, includePrerelease) {
  const versions = [];
  for (const rel of releases || []) {
    if (rel.draft) continue;
    if (rel.prerelease && !includePrerelease) continue;
    const asset = (rel.assets || []).find((a) => ASSET_RE.test(a.name || ""));
    const digest = String((asset && asset.digest) || "");
    if (!asset || !digest.startsWith("sha256:")) continue; // never offer an unverifiable ZIP
    versions.push({
      name: String(rel.tag_name || "").replace(/^v/, ""),
      hash: digest.slice("sha256:".length),
      artifact: asset.browser_download_url,
      created: rel.published_at || rel.created_at,
      downloads: asset.download_count || 0,
      updates: 0,
    });
  }
  versions.sort((a, b) => String(b.created).localeCompare(String(a.created)));
  if (!versions.length) return [];
  return [{
    id: 900001,
    name: PLUGIN_NAME,
    author: "Gillrv",
    description: "Wireless two-way file transfer between Steam Deck and phone/PC.",
    tags: ["files", "sharing", "transfer", "network"],
    versions,
    visible: true,
    image_url: `https://raw.githubusercontent.com/${REPO}/main/ScreenShots/Screenshot%202026-09-13%20at%2011.03.53.png`,
    downloads: versions.reduce((n, v) => n + v.downloads, 0),
    updates: 0,
    created: versions[versions.length - 1].created,
    updated: versions[0].created,
  }];
}

async function fetchReleases(env) {
  const headers = { "User-Agent": "deckyshare-store-worker", Accept: "application/vnd.github+json" };
  if (env && env.GITHUB_TOKEN) headers.Authorization = `Bearer ${env.GITHUB_TOKEN}`;
  const r = await fetch(`https://api.github.com/repos/${REPO}/releases?per_page=100`, {
    headers,
    cf: { cacheTtl: CACHE_SECONDS, cacheEverything: true },
  });
  if (!r.ok) throw new Error(`GitHub API ${r.status}`);
  return r.json();
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json", "Cache-Control": `public, max-age=${CACHE_SECONDS}` },
  });
}

export async function handle(request, env, fetchImpl = fetchReleases) {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  if (request.method !== "GET") return json({ error: "Method not allowed" }, 405);
  const path = new URL(request.url).pathname.replace(/\/+$/, "");
  if (path !== "/plugins" && path !== "/rc/plugins") {
    return json({ error: "Use /plugins (stable) or /rc/plugins (with release candidates)" }, 404);
  }
  try {
    return json(releasesToStore(await fetchImpl(env), path === "/rc/plugins"));
  } catch (e) {
    return json({ error: String((e && e.message) || e) }, 502);
  }
}

export default { fetch: (request, env) => handle(request, env) };
