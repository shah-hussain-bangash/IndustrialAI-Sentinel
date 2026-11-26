import { Component, Suspense, type ReactNode } from "react";
import { Button } from "./ui";

type Props = { resetKey: string; children: ReactNode };
export class ToolLoadBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidUpdate(previous: Props) {
    if (previous.resetKey !== this.props.resetKey && this.state.failed) this.setState({ failed: false });
  }
  render() {
    if (this.state.failed) return <section className="panel settings-card" role="alert">
      <h2>This tool could not open</h2>
      <p>Use the navigation to open another tool, or reload the portal to try again.</p>
      <p>Reloading clears unsaved form entries.</p>
      <Button onClick={() => window.location.reload()}>Reload portal</Button>
    </section>;
    return this.props.children;
  }
}

export function WorkspaceTool({ id, children }: { id: string; children: ReactNode }) {
  return <ToolLoadBoundary resetKey={id}><Suspense fallback={<section className="panel settings-card"><p role="status">Opening workspace tool…</p></section>}>
    {children}
  </Suspense></ToolLoadBoundary>;
}
