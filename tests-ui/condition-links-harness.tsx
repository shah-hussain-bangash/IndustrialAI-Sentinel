import { useState } from "react";
import { createRoot } from "react-dom/client";
import { ConditionInboxPage } from "../src/pages/ConditionInboxPage";
import "../src/styles.css";
import "../src/professional.css";
import "../src/experience.css";
let mode = "unavailable", calls = 0;
const id = "00000000-0000-4000-8000-000000000001";
window.fetch = async input => {
  calls++;
  if (String(input) !== `/api/condition-rules/matches/${id}/evidence`) throw new Error("Unexpected detail request");
  if (mode === "unavailable") return new Response(JSON.stringify({ detail: "Fixture denied" }), { status: 403 });
  return new Response(JSON.stringify({ match_id: mode === "mismatch" ? "another-match" : id,
    asset: { tag: "PRIVATE TAG MUST NOT APPEAR", name: "Fixture", site: "Other site" }, rule: { name: "Private rule", version: 1 } }));
};
function Harness() {
  const [version, setVersion] = useState(0), [allowed, setAllowed] = useState(true), [requestCount, setRequestCount] = useState(0);
  const scenario = (value: string) => { mode = value; setVersion(v => v + 1); };
  return <main style={{ padding: 24, maxWidth: 1000, margin: "auto" }}><h1>Condition link guards</h1><p>Isolated fixture; no live accounts or records.</p>
    <nav style={{ display: "flex", gap: 12 }}><button onClick={() => scenario("unavailable")}>Unavailable match</button>
      <button onClick={() => scenario("mismatch")}>Wrong response identity</button><button onClick={() => scenario("site")}>Different selected site</button>
      <button onClick={() => setAllowed(false)}>Restricted role</button><button onClick={() => setRequestCount(calls)}>Check request count</button></nav>
    <p>Requests: {requestCount}</p><ConditionInboxPage key={version} site="Selected site" canReview={allowed} refreshKey={0} matchId={id} />
  </main>;
}
createRoot(document.getElementById("root")!).render(<Harness />);
