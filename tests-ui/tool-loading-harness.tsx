import { lazy, useState, type ComponentType } from "react";
import { createRoot } from "react-dom/client";
import { WorkspaceTool } from "../src/components/WorkspaceTool";
import "../src/styles.css";

const Waiting = lazy(() => new Promise<{ default: ComponentType }>(() => {}));
const Missing = lazy(() => {
  const url = "/unavailable-test-tool.js";
  return import(/* @vite-ignore */ url);
});
function TestApp() {
  const [tool, setTool] = useState("healthy");
  return <main style={{ maxWidth: 800, margin: "40px auto", padding: 20 }}>
    <h1>Workspace tool loading test</h1><p>Isolated test fixture. No account or live application data is used.</p>
    <nav style={{ display: "flex", gap: 16, margin: "24px 0" }} aria-label="Test tools">
      <button onClick={() => setTool("healthy")}>Healthy test tool</button>
      <button onClick={() => setTool("waiting")}>Waiting test tool</button>
      <button onClick={() => setTool("missing")}>Unavailable test tool</button>
    </nav>
    <WorkspaceTool id={tool}>{tool === "waiting" ? <Waiting /> : tool === "missing" ? <Missing /> : <section className="panel settings-card"><h2>Healthy tool ready</h2><p>Navigation remains available after a loading failure.</p></section>}</WorkspaceTool>
  </main>;
}
createRoot(document.getElementById("root")!).render(<TestApp />);
