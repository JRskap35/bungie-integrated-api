/* Bungie-Integrated-API progress sync (Cloudflare Worker).
   Keeps the things a player enters by hand (armor pieces and stats logged, weapons marked Looking for, marks, the armor
   class picked) so they follow their Bungie sign in to any device, the way DIM keeps tags and notes.

   GET  /v1/progress   the signed in player's saved progress, or null
   PUT  /v1/progress   replace it (JSON object, at most 512 KB); answers {ok, savedAt}

   Every call carries the player's Bungie access token (Authorization: Bearer ...). The worker asks Bungie who the token
   belongs to (User/GetMembershipsForCurrentUser) and stores the data under that Bungie.net account id, so nobody can
   read or write anyone else's progress, and nothing here ever sees a password. A token's owner is remembered for ten
   minutes (by a SHA-256 of the token, never the token itself) to keep calls to Bungie down.

   Settings (wrangler.toml): VAULT (KV namespace), BUNGIE_API_KEY (the site's public API key), ALLOWED_ORIGINS (the site),
   BUNGIE_ORIGIN (the origin registered with the Bungie app, sent on the check because Bungie matches it to the key). */
const MAX_BYTES = 512 * 1024;

export default {
  async fetch(req, env) {
    const allowed = String(env.ALLOWED_ORIGINS || "").split(",").map(s => s.trim()).filter(Boolean);
    const origin = req.headers.get("Origin") || "";
    const cors = {
      "Access-Control-Allow-Origin": allowed.includes(origin) ? origin : (allowed[0] || "*"),
      "Access-Control-Allow-Methods": "GET, PUT, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type",
      "Access-Control-Max-Age": "86400",
      "Vary": "Origin",
    };
    const json = (data, status = 200) => new Response(JSON.stringify(data), {
      status, headers: {...cors, "Content-Type": "application/json", "Cache-Control": "no-store"}});

    if (req.method === "OPTIONS") return new Response(null, {status: 204, headers: cors});
    const url = new URL(req.url);
    if (url.pathname === "/" || url.pathname === "/health") return json({ok: true, service: "bia-progress"});
    if (url.pathname !== "/v1/progress") return json({error: "not_found"}, 404);
    if (origin && allowed.length && !allowed.includes(origin)) return json({error: "origin_not_allowed"}, 403);

    const auth = req.headers.get("Authorization") || "";
    const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
    if (!token) return json({error: "signed_out"}, 401);
    let who;
    try { who = await whoIs(token, env); } catch (e) { return json({error: "bungie_unreachable"}, 502); }
    if (!who) return json({error: "signed_out"}, 401);
    const key = "progress:" + who;

    if (req.method === "GET") {
      const v = await env.VAULT.get(key);
      return new Response(v || "null", {headers: {...cors, "Content-Type": "application/json", "Cache-Control": "no-store"}});
    }
    if (req.method === "PUT") {
      const body = await req.text();
      if (body.length > MAX_BYTES) return json({error: "too_big"}, 413);
      let d;
      try { d = JSON.parse(body); } catch (e) { return json({error: "bad_json"}, 400); }
      if (!d || typeof d !== "object" || Array.isArray(d)) return json({error: "bad_shape"}, 400);
      const keep = {v: 1};
      for (const k of ["marks", "armor", "armorLook"]) {
        const x = d[k] === undefined ? {} : d[k];
        if (!x || typeof x !== "object" || Array.isArray(x)) return json({error: "bad_shape", field: k}, 400);
        keep[k] = x;
      }
      if (typeof d.cls === "string" && d.cls.length < 20) keep.cls = d.cls;
      keep.savedAt = Date.now();
      await env.VAULT.put(key, JSON.stringify(keep));
      return json({ok: true, savedAt: keep.savedAt});
    }
    return json({error: "method_not_allowed"}, 405);
  },
};

async function whoIs(token, env) {
  const h = await sha256(token);
  const cached = await env.VAULT.get("tok:" + h);
  if (cached) return cached;
  const headers = {"X-API-Key": env.BUNGIE_API_KEY, "Authorization": "Bearer " + token};
  if (env.BUNGIE_ORIGIN) headers["Origin"] = env.BUNGIE_ORIGIN;
  const r = await fetch("https://www.bungie.net/Platform/User/GetMembershipsForCurrentUser/", {headers});
  if (r.status === 401) return null;
  const j = await r.json().catch(() => null);
  if (!j) throw new Error("bungie " + r.status);
  if (j.ErrorCode !== 1) {
    if (j.ErrorStatus === "WebAuthRequired" || j.ErrorCode === 99 || j.ErrorCode === 2111 || j.ErrorCode === 2112) return null;
    throw new Error("bungie " + j.ErrorStatus);
  }
  const id = j.Response && j.Response.bungieNetUser && j.Response.bungieNetUser.membershipId;
  if (!id) return null;
  await env.VAULT.put("tok:" + h, String(id), {expirationTtl: 600});
  return String(id);
}

async function sha256(s) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("");
}
