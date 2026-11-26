import { useState } from "react";
import { createRoot } from "react-dom/client";
import { AttentionPanel } from "../src/components/AttentionPanel";
import "../src/styles.css";
import "../src/professional.css";
import "../src/experience.css";

let mode = "matches";
let calls = 0;
let release: (() => void) | null = null;
window.fetch = async input => {
  if (!String(input).startsWith("/api/condition-rules/inbox?")) throw new Error("Unexpected fixture request");
  calls++;
  const requestedMode = mode;
  if (requestedMode === "waiting") await new Promise<void>(resolve => { release = resolve; });
  if (requestedMode === "error") return new Response(JSON.stringify({ detail: "Isolated connection failure" }), { status: 503 });
  const site = new URL(String(input), window.location.origin).searchParams.get("site") || "Fixture Site A";
  return new Response(JSON.stringify({ total_matching: requestedMode === "empty" ? 0 : 6,
    items: requestedMode === "empty" ? [] : Array.from({ length: 6 }, (_, i) => ({ id: String(i), asset_tag: "TEST-" + i,
      site, name: requestedMode === "waiting" ? "STALE RESULT MUST NOT APPEAR" : "Synthetic vibration rule",
      rule_version: 3, signal_state: i === 0 ? "paused" : "active", triggered_at: 1795650000 })) }), { status: 200 });
};
function Harness() {
  const [key, setKey] = useState(0), [site, setSite] = useState("Fixture Site A"), [role, setRole] = useState(true);
  const [opened, setOpened] = useState(true), [action, setAction] = useState("None"), [requestCount, setRequestCount] = useState(0);
  function scenario(next: string) { mode = next; setKey(k => k + 1); setOpened(true); }
  return <main style={{ padding: 24 }}><h1>Attention panel acceptance fixture</h1>
    <p>Synthetic data only. No accounts, credentials or live records.</p>
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      <button onClick={() => scenario("matches")}>Six matches</button><button onClick={() => scenario("empty")}>Empty result</button>
      <button onClick={() => { mode = "error"; }}>Make next refresh fail</button>
      <button onClick={() => scenario("waiting")}>Hold old request</button>
      <button onClick={() => { mode = "matches"; setSite("Fixture Site B"); }}>Switch to Site B</button>
      <button onClick={() => release?.()}>Release old request</button>
      <button onClick={() => { setRole(false); setKey(k => k + 1); }}>Restricted role</button>
      <button onClick={() => setRequestCount(calls)}>Read request count</button>
    </div><p>Requests: {requestCount}. Last navigation: {action}.</p>
    <div style={{ position: "relative", marginTop: 20, width: "min(460px, 100%)", height: 720 }}>
      {opened && <AttentionPanel key={`${key}:${site}:${role}`} site={site} canReview={role} episodes={[]}
        close={() => setOpened(false)} openConditions={() => setAction("Condition inbox")}
        openAsset={() => setAction("Equipment")} openMonitor={() => setAction("Monitoring")} />}
    </div>
  </main>;
}
createRoot(document.getElementById("root")!).render(<Harness />);
