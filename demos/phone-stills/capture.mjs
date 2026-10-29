// screenshots a page one screen at a time at phone size, for stitching into the landing page's phone stills
// node capture.mjs <url> <outdir> [width=390] [height=750] [dpr=2]
// the sticky header is shot once on its own and hidden in later screens, so the stitched page has it only at the top
import { spawn, spawnSync } from "node:child_process";
import { writeFileSync, mkdtempSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [url, outdir, w = "390", h = "750", dpr = "2"] = process.argv.slice(2);
mkdirSync(outdir, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const port = 9300 + Math.floor(Math.random() * 500);
const edge = spawn(EDGE, ["--headless=new", "--hide-scrollbars", "--no-first-run", `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "ui-"))}`, "about:blank"], { stdio: "ignore" });
let ws, id = 0;
const pending = new Map();
const send = (method, params = {}) => Promise.race([new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); }), sleep(20000).then(() => ({ timeout: method }))]);
const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }); return r.timeout ? 'TIMEOUT' : r.exceptionDetails ? "EXC " + JSON.stringify(r.exceptionDetails).slice(0, 300) : r.result.value; };
try {
  let targets;
  for (let k = 0; k < 50; k++) { try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); if (targets.length) break; } catch {} await sleep(200); }
  ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d.result || d.error); pending.delete(d.id); } };
  await send("Page.enable"); await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: +w, height: +h, deviceScaleFactor: +dpr, mobile: true });
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });  // final states, no transitions mid-shot
  await send("Page.navigate", { url });
  await sleep(3000);
  // walk down once so lazy images and reveals load, then back to the top
  await ev(`(async () => { document.documentElement.style.scrollBehavior = 'auto'; for (let y = 0; y < document.documentElement.scrollHeight; y += 300) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 120)); } scrollTo(0, 0); await Promise.race([Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))), new Promise((r) => setTimeout(r, 5000))]); await document.fonts.ready; })()`);
  await sleep(1500);
  const info = await ev(`(() => { const hd = [...document.querySelectorAll('body *')].find((e) => ['sticky', 'fixed'].includes(getComputedStyle(e).position) && e.getBoundingClientRect().top < 200 && e.offsetHeight < innerHeight / 3);
    const b = hd && hd.getBoundingClientRect(); if (hd) hd.setAttribute('data-shot-sticky', '');
    return { H: document.documentElement.scrollHeight, vh: innerHeight, head: hd ? { tag: hd.tagName.toLowerCase() + '.' + hd.className, top: Math.round(b.top), h: Math.round(b.height) } : null }; })()`);
  console.log(JSON.stringify(info));
  const shot = async (name, clip) => { const s = await send("Page.captureScreenshot", { format: "png", clip: clip ? { ...clip, scale: 1 } : undefined }); writeFileSync(join(outdir, name), Buffer.from(s.data, "base64")); };
  if (info.head) await shot("head.png", { x: 0, y: info.head.top, width: +w, height: info.head.h });
  const ys = [];
  for (let y = 0; y < info.H; y += info.vh) ys.push(Math.min(y, info.H - info.vh));
  for (let i = 0; i < ys.length; i++) {
    await ev(`(() => { scrollTo(0, ${ys[i]}); const hd = document.querySelector('[data-shot-sticky]'); if (hd) hd.style.visibility = ${i ? "'hidden'" : "''"}; })()`);
    await sleep(500);
    const real = await ev("scrollY");
    await shot(`s${String(i).padStart(2, "0")}.png`);
    ys[i] = real;
  }
  writeFileSync(join(outdir, "shots.json"), JSON.stringify({ ...info, w: +w, dpr: +dpr, ys }));
  console.log("screens", ys.length, "offsets", ys.join(","));
} finally {
  spawnSync("taskkill", ["/PID", String(edge.pid), "/T", "/F"], { stdio: "ignore" });
}
process.exit(0);
