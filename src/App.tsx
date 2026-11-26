import { useState, useEffect, useCallback, useRef, lazy } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Bell,
  BookOpen,
  Box,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Download,
  GitBranch,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  Radio,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  Upload,
  X,
  type LucideIcon,
  FlaskConical,
} from "lucide-react";
import {
  api,
  post,
  setCsrf,
  human,
  type User,
  type Asset,
  type Episode,
  type Investigation,
  type WorkOrder,
  type DocumentInfo,
  type AuditEvent,
  type Overview,
  type Operations,
  type Preferences,
} from "./api";
import { initials, Badge, Button, Spinner, Modal } from "./components/ui";
import { LoginScreen, LoginChoices } from "./components/Login";
import { AccountLinkScreen } from "./components/AccountRecovery";
import { AdminMfaPanel } from "./components/AdminMfaPanel";
import type { Data, Page } from "./types";
import { WorkspaceTool } from "./components/WorkspaceTool";
import { AttentionPanel } from "./components/AttentionPanel";
import { headerImages } from "./lib/headerImages";
import { investigationIdFromHash } from "./lib/investigationRoute";
import { conditionMatchIdFromHash } from "./lib/conditionMatchRoute";
const OrganizationPage = lazy(() => import("./pages/OrganizationPage").then(module => ({ default: module.OrganizationPage })));
const TeamPage = lazy(() => import("./pages/TeamPage").then(module => ({ default: module.TeamPage })));
const ProductionPage = lazy(() => import("./pages/ProductionPage").then(module => ({ default: module.ProductionPage })));
import { OverviewPage } from "./pages/OverviewPage";
const AssetsPage = lazy(() => import("./pages/AssetsPage").then(module => ({ default: module.AssetsPage })));
const MonitorPage = lazy(() => import("./pages/MonitorPage").then(module => ({ default: module.MonitorPage })));
const IntelligencePage = lazy(() => import("./pages/IntelligencePage").then(module => ({ default: module.IntelligencePage })));
const KnowledgePage = lazy(() => import("./pages/KnowledgePage").then(module => ({ default: module.KnowledgePage })));
const OrdersPage = lazy(() => import("./pages/OrdersPage").then(module => ({ default: module.OrdersPage })));
const ActivityPage = lazy(() => import("./pages/ActivityPage").then(module => ({ default: module.ActivityPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then(module => ({ default: module.SettingsPage })));
const ConditionInboxPage = lazy(() => import("./pages/ConditionInboxPage").then(module => ({ default: module.ConditionInboxPage })));
const ReliabilityPage = lazy(() => import("./pages/ReliabilityPage").then(module => ({ default: module.ReliabilityPage })));
const SensorsPage = lazy(() => import("./pages/SensorsPage").then(module => ({ default: module.SensorsPage })));
import { AssetDrawer } from "./components/dialogs/AssetDrawer";
import { AssetForm } from "./components/dialogs/AssetForm";
import { NewInvestigation } from "./components/dialogs/NewInvestigation";
import { UploadDocument } from "./components/dialogs/UploadDocument";
import { DocumentViewer } from "./components/dialogs/DocumentViewer";
import { InvestigationModal } from "./components/dialogs/InvestigationModal";
import { OrderModal } from "./components/dialogs/OrderModal";

const pages: { id: Page; label: string; icon: LucideIcon; group: string }[] = [
  {
    id: "overview",
    label: "Overview",
    icon: LayoutDashboard,
    group: "WORKSPACE",
  },
  { id: "assets", label: "Asset registry", icon: Box, group: "WORKSPACE" },
  { id: "monitor", label: "Live monitoring", icon: Radio, group: "WORKSPACE" },
  {
    id: "sensors",
    label: "Sensor registry",
    icon: Activity,
    group: "WORKSPACE",
  },
  {
    id: "intelligence",
    label: "AI investigations",
    icon: Sparkles,
    group: "INTELLIGENCE",
  },
  { id: "conditions", label: "Condition inbox", icon: Bell, group: "INTELLIGENCE" },
  {
    id: "knowledge",
    label: "Knowledge base",
    icon: BookOpen,
    group: "INTELLIGENCE",
  },
  {
    id: "reliability",
    label: "Reliability lab",
    icon: FlaskConical,
    group: "INTELLIGENCE",
  },
  {
    id: "orders",
    label: "Work orders",
    icon: ClipboardCheck,
    group: "OPERATIONS",
  },
  {
    id: "organization",
    label: "Organization & sites",
    icon: Box,
    group: "OPERATIONS",
  },
  {
    id: "team", label: "Team & access", icon: ShieldCheck, group: "OPERATIONS",
  },
  {
    id: "activity",
    label: "Activity & audit",
    icon: GitBranch,
    group: "OPERATIONS",
  },
  {
    id: "settings",
    label: "Workspace settings",
    icon: Settings2,
    group: "OPERATIONS",
  },
  {
    id: "production",
    label: "Production workspace",
    icon: ShieldCheck,
    group: "PRODUCT DESIGN",
  },
];
const titles: Record<Page, string> = {
  conditions: "Condition inbox",
  team: "Team & access",
  organization: "Organization & sites",
  production: "Production workspace",
  overview: "Operations overview",
  assets: "Asset registry",
  monitor: "Live sensor monitoring",
  sensors: "Sensor registry",
  intelligence: "AI investigations",
  knowledge: "Industrial knowledge base",
  reliability: "Reliability lab",
  orders: "Work orders",
  activity: "Activity & audit",
  settings: "Workspace settings",
};
const descriptions: Record<Page, string> = {
  conditions: "Find equipment signals that need review, with clear ownership and history.",
  team: "Bring your team together with clear roles and controlled site access.",
  organization: "Manage your company profile, sites and equipment hierarchy.",
  production:
    "Explore platform modules, review workflows and prepare the path to a production pilot.",
  overview: "A clear view of equipment condition. A confident next step.",
  assets:
    "Explore equipment condition, operating history and maintenance context.",
  monitor:
    "Follow vibration, temperature, pressure and flow across your assets.",
  sensors:
    "Manage sensor identity, canonical units and reporting expectations.",
  intelligence:
    "Turn equipment observations into reviewable maintenance recommendations.",
  knowledge:
    "Bring procedures and maintenance evidence into one searchable workspace.",
  reliability:
    "Prioritize with context. Compare measured signals. Explore what-if scenarios.",
  orders:
    "Plan, dispatch and track work through a controlled approval process.",
  activity:
    "Trace observations, decisions and maintenance outcomes across your workspace.",
  settings:
    "Manage your experience and inspect the local system configuration.",
};

export default function App() {
  const [accountToken, setAccountToken] = useState(() => window.location.hash.startsWith('#account-link=') ? window.location.hash.slice('#account-link='.length) : '');
  useEffect(()=>{if(accountToken)window.history.replaceState(null,'',window.location.pathname+window.location.search+'#account-link');},[accountToken]);
  const [user, setUser] = useState<User | null>(null),
    [authReady, setAuthReady] = useState(false);
  const [page, setPage] = useState<Page>(() => {
      const id = window.location.hash.slice(1).split("/")[0];
      return pages.find((p) => p.id === id)?.id || "overview";
    }),
    [site, setSite] = useState(""),
    [search, setSearch] = useState("");
  const [data, setData] = useState<Data | null>(null),
    [loading, setLoading] = useState(false),
    [loadError, setLoadError] = useState("");
  const [toast, setToast] = useState<{
      message: string;
      error?: boolean;
    } | null>(null),
    [busy, setBusy] = useState(false),
    [mobile, setMobile] = useState(false);
  const [live, setLive] = useState(false),
    [scenario, setScenario] = useState("normal"),
    [refreshKey, setRefreshKey] = useState(0);
  const [assetId, setAssetId] = useState<string | null>(null),
    [documentId, setDocumentId] = useState<string | null>(null),
    [documentPage, setDocumentPage] = useState(1);
  const [newAsset, setNewAsset] = useState(false),
    [newInvestigation, setNewInvestigation] = useState(false),
    [uploadDoc, setUploadDoc] = useState(false);
  const [investigationId, setInvestigationId] = useState<string | null>(() => investigationIdFromHash(window.location.hash)),
    [orderId, setOrderId] = useState<string | null>(null);
  const [conditionMatchId, setConditionMatchId] = useState<string | null>(() => conditionMatchIdFromHash(window.location.hash));
  const [notifications, setNotifications] = useState(false),
    [profile, setProfile] = useState(false),
    [switching, setSwitching] = useState(false);
  useEffect(() => { setNotifications(false); }, [user?.id, user?.role, site]);
  const [prefs, setPrefs] = useState<Preferences>({
    compact: false,
    email_digest: false,
    display_timezone: "Asia/Dubai",
  });
  const notify = useCallback(
    (message: string, error = false) => setToast({ message, error }),
    [],
  );
  const refresh = useCallback(() => setRefreshKey((x) => x + 1), []);
  const openDocument = useCallback((id: string, page = 1) => {
    setDocumentPage(page);
    setDocumentId(id);
  }, []);
  useEffect(() => {
    api<{ user: User; csrf: string }>("/auth/me")
      .then((r) => {
        setCsrf(r.csrf);
        setUser(r.user);
      })
      .catch(() => {})
      .finally(() => setAuthReady(true));
  }, []);
  useEffect(() => {
    const expired = () => {
      setUser(null);
      setData(null);
      setLive(false);
      notify("Your session expired. Please sign in again.", true);
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, [notify]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    if (user)
      api<Preferences>("/preferences")
        .then(setPrefs)
        .catch(() => {});
  }, [user]);
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setLoading(true);
    setLoadError("");
    const q = site ? `?site=${encodeURIComponent(site)}` : "";
    Promise.all([
      api<Overview>("/overview" + q),
      api<Asset[]>("/assets" + q),
      api<Episode[]>("/episodes" + q),
      api<Investigation[]>("/investigations" + q),
      api<WorkOrder[]>("/work-orders" + q),
      api<DocumentInfo[]>("/documents" + q),
      api<AuditEvent[]>("/activity" + q),
      api<Operations>("/operations"),
    ])
      .then(
        ([
          overview,
          assets,
          episodes,
          investigations,
          orders,
          documents,
          activity,
          operations,
        ]) => {
          if (!cancelled)
            setData({
              overview,
              assets,
              episodes,
              investigations,
              orders,
              documents,
              activity,
              operations,
            });
        },
      )
      .catch((e) => {
        if (!cancelled) setLoadError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, site, refreshKey]);
  const run = useCallback(
    async (action: () => Promise<unknown>, success: string) => {
      setBusy(true);
      try {
        await action();
        notify(success);
        refresh();
        return true;
      } catch (e) {
        notify((e as Error).message, true);
        return false;
      } finally {
        setBusy(false);
      }
    },
    [notify, refresh],
  );
  const simulationBusy = useRef(false);
  useEffect(() => {
    if (!live || !user) return;
    const timer = setInterval(async () => {
      if (simulationBusy.current) return;
      simulationBusy.current = true;
      try {
        await post("/simulation/tick", { scenario });
        refresh();
      } catch (e) {
        setLive(false);
        notify((e as Error).message, true);
      } finally {
        simulationBusy.current = false;
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [live, scenario, user, refresh, notify]);
  useEffect(() => {
    const changed = () => {
      if(window.location.hash.startsWith('#account-link=')) { setAccountToken(window.location.hash.slice('#account-link='.length)); return; }
      const id = window.location.hash.slice(1).split("/")[0];
      const destination = pages.find((p) => p.id === id);
      if (destination) {
        setPage(destination.id);
        setMobile(false);
        const linkedId = investigationIdFromHash(window.location.hash);
        const linkedMatchId = conditionMatchIdFromHash(window.location.hash);
        setConditionMatchId(linkedMatchId);
        setInvestigationId(linkedId);
        if (linkedId || linkedMatchId) { setData(null); setSite(""); setRefreshKey(value => value + 1); }
      }
    };
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  function navigate(next: Page) {
    window.location.hash = next;
    setPage(next);
    setMobile(false);
    setSearch("");
  }
  function signedIn(u: User, csrf: string) {
    setCsrf(csrf);
    setUser(u);
    setSite("");
    setData(null);
    setSwitching(false);
    setProfile(false);
    notify(`Welcome, ${u.name.split(" ")[0]}.`);
  }
  async function logout() {
    await run(() => post("/auth/logout", {}), "Signed out.");
    setUser(null);
    setData(null);
    setLive(false);
  }
  const canOperate = !!user && ["engineer", "admin"].includes(user.role);
  const toastNode = toast && (
    <div className={`toast ${toast.error ? "error" : ""}`} role="status">
      {toast.error ? <TriangleAlert size={18} /> : <CheckCircle2 size={18} />}
      <span>{toast.message}</span>
      <button aria-label="Dismiss notification" onClick={() => setToast(null)}>
        <X size={15} />
      </button>
    </div>
  );
  if (!authReady)
    return (
      <div className="boot">
        <img src="/sentinel.svg" width="56" alt="" />
        <Spinner />
      </div>
    );
  if (accountToken) return <AccountLinkScreen token={accountToken} onDone={()=>{setAccountToken('');window.location.hash='overview';setUser(null);}}/>;
  if (!user)
    return (
      <>
        <LoginScreen onLogin={signedIn} />
        {toastNode}
      </>
    );
  if(user.mfa_setup_required)return <main className="mfa-gate"><h1>Secure your administrator account</h1><p>Company policy requires authenticator enrollment before you can access the workspace.</p><AdminMfaPanel onRemoved={()=>setUser(null)} onComplete={()=>window.location.reload()}/><Button onClick={logout}>Sign out</Button></main>;
  const current = pages.find((p) => p.id === page)!;
  const searchAssets = search
    ? data?.assets
        .filter((a) =>
          `${a.tag} ${a.name} ${a.kind}`
            .toLowerCase()
            .includes(search.toLowerCase()),
        )
        .slice(0, 5)
    : [];
  const activeInv = data?.investigations.find((i) => i.id === investigationId);
  const activeOrder = data?.orders.find((o) => o.id === orderId);
  return (
    <div className={`app-shell ${prefs.compact ? "compact" : ""}`}>
      <a
        className="skip-link"
        href="#workspace-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("workspace-content")?.focus();
        }}
      >
        Skip to workspace
      </a>
      {mobile && <div className="nav-shade" onClick={() => setMobile(false)} />}
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <a
          className="brand"
          href="#overview"
          onClick={(e) => {
            e.preventDefault();
            navigate("overview");
          }}
        >
          <img src="/sentinel.svg" alt="" />
          <div>
            <strong>
              sentinel<span>AI</span>
            </strong>
            <small>INDUSTRIAL INTELLIGENCE</small>
          </div>
        </a>
        <div className="workspace-card">
          <span className="workspace-icon">
            <Box size={18} />
          </span>
          <div>
            <strong>Energy operations</strong>
            <small>Demonstration workspace</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <nav aria-label="Main navigation">
          {pages.map((p, i) => (
            <div key={p.id}>
              {(i === 0 || p.group !== pages[i - 1].group) && (
                <div className="nav-group">{p.group}</div>
              )}
              <button
                className={`nav-item ${page === p.id ? "active" : ""}`}
                onClick={() => navigate(p.id)}
                aria-current={page === p.id ? "page" : undefined}
              >
                <p.icon size={18} />
                <span>{p.label}</span>
                {p.id === "intelligence" &&
                  !!data?.overview.stats.pending_reviews && (
                    <b>{data.overview.stats.pending_reviews}</b>
                  )}
                {p.id === "monitor" && (
                  <i className={live ? "pulse-dot" : ""} />
                )}
              </button>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="system-card">
            <div>
              <span className="signal-dot" />
              Local demo environment
            </div>
            <p>Simulated sensors. Real workflows.</p>
            <button onClick={() => navigate("settings")}>
              View system status <ArrowUpRight size={13} />
            </button>
          </div>
          <button
            className="sidebar-help"
            onClick={() =>
              notify(
                "Start with Asset registry, then Investigate, Review and Work orders. Switch demo accounts to review and plan work.",
              )
            }
          >
            <CircleHelp size={17} />
            Quick walkthrough
            <ArrowUpRight size={14} />
          </button>
          <div className="sidebar-user">
            <span className="avatar">{initials(user.name)}</span>
            <div>
              <strong>{user.name}</strong>
              <small>{human(user.role)} · UAE workspace</small>
            </div>
            <button aria-label="Sign out" title="Sign out" onClick={logout}>
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-btn mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Menu size={21} />
            </button>
            <span className="breadcrumb">
              Workspace <ChevronRight size={13} />
              <strong>{current.label}</strong>
              <span className="workspace-environment">Demo workspace</span>
            </span>
          </div>
          <div className="topbar-tools">
            <div className="global-search">
              <Search size={16} />
              <input
                aria-label="Search assets"
                placeholder="Search assets, equipment…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <kbd>/</kbd>
              {search && (
                <div className="search-results">
                  {searchAssets?.length ? (
                    searchAssets.map((a) => (
                      <button
                        key={a.id}
                        onClick={() => {
                          setAssetId(a.id);
                          setSearch("");
                        }}
                      >
                        <Box size={16} />
                        <span>
                          <strong>{a.tag}</strong> {a.name}
                        </span>
                        <ChevronRight size={14} />
                      </button>
                    ))
                  ) : (
                    <p>No matching assets in this site.</p>
                  )}
                </div>
              )}
            </div>
            <span className="header-divider" />
            <span className="header-role">{human(user.role)}</span>
            <div className="popover-parent">
              <button
                className="icon-btn notification-btn"
                aria-label="Notifications"
                aria-expanded={notifications}
                onClick={() => setNotifications(!notifications)}
              >
                <Bell size={19} />
              </button>
              {notifications && (
                <AttentionPanel key={`${user.id}:${user.role}:${site}`} site={site} canReview={canOperate}
                  episodes={!loading && !loadError && data ? data.episodes : null} close={() => setNotifications(false)}
                  openConditions={() => { navigate("conditions"); setNotifications(false); }}
                  openAsset={id => { setAssetId(id); setNotifications(false); }}
                  openMonitor={() => { navigate("monitor"); setNotifications(false); }} />
              )}
            </div>
            <div className="popover-parent">
              <button
                className="avatar small"
                aria-label="Account menu"
                onClick={() => setProfile(!profile)}
              >
                {initials(user.name)}
              </button>
              {profile && (
                <div className="popover profile-popover">
                  <strong>{user.name}</strong>
                  <small>{user.email}</small>
                  <Badge value="healthy">{human(user.role)}</Badge>
                  <button
                    onClick={() => {
                      setSwitching(true);
                      setLive(false);
                    }}
                  >
                    <RefreshCw size={15} />
                    Switch demo account
                  </button>
                  <button onClick={logout}>
                    <LogOut size={15} />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main id="workspace-content" tabIndex={-1}>
          <div
            className={`page-heading ${["overview", "monitor", "production"].includes(page) ? "" : "photographic-page-heading"}`}
          >
            {!["overview", "monitor", "production"].includes(page) && (
              <>
                <img
                  className="page-heading-photograph"
                  src={`/assets/photos/${headerImages[page].file}.jpg`}
                  style={{ objectPosition: headerImages[page].position }}
                  alt=""
                  fetchPriority="high"
                />
                <span className="page-heading-image-caption">
                  {headerImages[page].caption} · Illustrative photograph
                </span>
              </>
            )}
            <div>
              <div className="eyebrow">
                INDUSTRIAL OPERATIONS <span>/</span>
                {page === "overview" ? "COMMAND CENTER" : current.group}
              </div>
              <h1>{titles[page]}</h1>
              <p>{descriptions[page]}</p>
            </div>
            <div className="page-actions">
              {page === "overview" && (
                <>
                  <a className="btn" href="/api/export/assets.csv" download>
                    <Download size={15} />
                    Export assets
                  </a>
                  <Button
                    className="primary"
                    icon={Plus}
                    onClick={() => setNewInvestigation(true)}
                    disabled={
                      !["engineer", "planner", "admin"].includes(user.role)
                    }
                  >
                    New investigation
                  </Button>
                </>
              )}
              {page === "assets" && (
                <Button
                  className="primary"
                  icon={Plus}
                  onClick={() => setNewAsset(true)}
                  disabled={!canOperate}
                >
                  Register asset
                </Button>
              )}
              {page === "intelligence" && (
                <Button
                  className="primary"
                  icon={Plus}
                  onClick={() => setNewInvestigation(true)}
                  disabled={
                    !["engineer", "planner", "admin"].includes(user.role)
                  }
                >
                  New investigation
                </Button>
              )}
              {page === "knowledge" && (
                <Button
                  className="primary"
                  icon={Upload}
                  onClick={() => setUploadDoc(true)}
                  disabled={!canOperate}
                >
                  Upload document
                </Button>
              )}
              {page === "orders" && (
                <Button
                  className="primary"
                  icon={Plus}
                  onClick={() => navigate("intelligence")}
                >
                  Plan from an approval
                </Button>
              )}
            </div>
          </div>
          <div className="scope-bar">
            <div className="scope-select">
              <span className="scope-icon">
                <Box size={14} />
              </span>
              <select
                aria-label="Select site"
                value={site}
                onChange={(e) => setSite(e.target.value)}
              >
                <option value="">All permitted sites</option>
                {user.sites.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
              <ChevronDown size={13} />
            </div>
            <div className="scope-status">
              <span className="signal-dot" />
              {live ? "Simulation streaming" : "Demo data connected"}
              <span className="dot-separator">·</span>
              <span>{loading ? "Syncing…" : "Times in GST (UTC+4)"}</span>
              <button
                className="icon-btn"
                aria-label="Refresh data"
                onClick={refresh}
              >
                <RefreshCw size={14} className={loading ? "spin" : ""} />
              </button>
            </div>
          </div>
          {loadError && (
            <div className="error-banner">
              <TriangleAlert size={18} />
              <span>{loadError}</span>
              <Button onClick={refresh}>Retry</Button>
            </div>
          )}
          {!data ? (
            <Spinner />
          ) : (
            <WorkspaceTool id={page}>
              {page === "organization" && (
                <OrganizationPage
                  openAsset={setAssetId}
                  selectedSite={site}
                  selectSite={setSite}
                />
              )}
              {page === "team" && <TeamPage user={user} />}
              {page === "production" && (
                <ProductionPage data={data} navigate={navigate} />
              )}
              {page === "overview" && (
                <OverviewPage
                  data={data}
                  openAsset={setAssetId}
                  navigate={navigate}
                  openInvestigation={setInvestigationId}
                />
              )}
              {page === "assets" && (
                <AssetsPage assets={data.assets} openAsset={setAssetId} />
              )}
              {page === "monitor" && (
                <MonitorPage
                  assets={data.assets}
                  episodes={data.episodes}
                  live={live}
                  setLive={setLive}
                  scenario={scenario}
                  setScenario={setScenario}
                  canOperate={canOperate}
                  refreshKey={refreshKey}
                  openAsset={setAssetId}
                  run={run}
                />
              )}
              {page === "intelligence" && (
                <IntelligencePage
                  data={data}
                  open={setInvestigationId}
                  newInvestigation={() => setNewInvestigation(true)}
                  user={user}
                />
              )}
              {page === "knowledge" && (
                <KnowledgePage
                  documents={data.documents}
                  openDoc={openDocument}
                  site={site}
                />
              )}
              {page === "orders" && (
                <OrdersPage
                  orders={data.orders}
                  open={setOrderId}
                  navigate={navigate}
                />
              )}
              {page === "activity" && <ActivityPage events={data.activity} />}
              {page === "conditions" && <ConditionInboxPage key={user.id} site={site} refreshKey={refreshKey} canReview={canOperate} matchId={conditionMatchId} />}
              {page === "sensors" && (
                <SensorsPage
                  site={site}
                  refreshKey={refreshKey}
                  canConfigure={canOperate}
                  openAsset={setAssetId}
                />
              )}
              {page === "reliability" && (
                <ReliabilityPage
                  assets={data.assets}
                  site={site}
                  refreshKey={refreshKey}
                  canSave={canOperate}
                  openAsset={setAssetId}
                />
              )}
              {page === "settings" && (
                <SettingsPage
                  onPasswordChanged={() => {
                    setLive(false);
                    setCsrf("");
                    setData(null);
                    setUser(null);
                    setProfile(false);
                    setSwitching(false);
                    notify("Password updated. Sign in with your new password.");
                  }}
                  user={user}
                  operations={data.operations}
                  prefs={prefs}
                  setPrefs={setPrefs}
                  run={run}
                  switchAccount={() => setSwitching(true)}
                />
              )}
            </WorkspaceTool>
          )}
          <footer className="workspace-footer">
            <span>
              <img src="/sentinel.svg" alt="" />
              IndustrialAI Sentinel <i>·</i>Reference implementation
            </span>
            <span>
              <ShieldCheck size={13} />
              Human approval required for maintenance actions
            </span>
          </footer>
        </main>
      </div>
      {assetId && (
        <AssetDrawer
          id={assetId}
          onClose={() => setAssetId(null)}
          refreshKey={refreshKey}
          onInvestigate={(id) => {
            setAssetId(null);
            run(async () => {
              const r = await post<Investigation>("/investigations", {
                asset_id: id,
              });
              setInvestigationId(r.id);
              setPage("intelligence");
            }, "Investigation prepared with source evidence.");
          }}
          canInvestigate={["engineer", "planner", "admin"].includes(user.role)}
          busy={busy}
        />
      )}
      {newAsset && (
        <AssetForm
          user={user}
          onClose={() => setNewAsset(false)}
          onSubmit={(body) =>
            run(async () => {
              await post("/assets", body);
              setNewAsset(false);
            }, "Asset registered. Use Live monitoring and Step once to generate demo readings.")
          }
          busy={busy}
        />
      )}
      {newInvestigation && data && (
        <NewInvestigation
          assets={data.assets}
          onClose={() => setNewInvestigation(false)}
          busy={busy}
          onSubmit={(id) =>
            run(async () => {
              const r = await post<Investigation>("/investigations", {
                asset_id: id,
              });
              setNewInvestigation(false);
              setInvestigationId(r.id);
              setPage("intelligence");
            }, "Investigation prepared. Review the evidence before approval.")
          }
        />
      )}
      {uploadDoc && (
        <UploadDocument
          user={user}
          site={site}
          onClose={() => setUploadDoc(false)}
          busy={busy}
          onSubmit={(form) =>
            run(async () => {
              await api("/documents/upload", { method: "POST", body: form });
              setUploadDoc(false);
            }, "Document parsed and added to authorized retrieval.")
          }
        />
      )}
      {investigationId && investigationIdFromHash(window.location.hash) === investigationId && data && !loading && !activeInv && (
        <Modal title="Investigation unavailable" description="This record is missing or outside your current site access." onClose={() => { setInvestigationId(null); window.location.hash = "intelligence"; }}>
          <p>Return to AI investigations to choose an available record.</p>
        </Modal>
      )}
      {activeInv && (
        <InvestigationModal
          inv={activeInv}
          user={user}
          busy={busy}
          onClose={() => { setInvestigationId(null); if (investigationIdFromHash(window.location.hash)) window.location.hash = "intelligence"; }}
          openDoc={openDocument}
          run={run}
        />
      )}
      {activeOrder && (
        <OrderModal
          order={activeOrder}
          user={user}
          busy={busy}
          onClose={() => setOrderId(null)}
          run={run}
        />
      )}
      {documentId && (
        <DocumentViewer
          id={documentId}
          initialPage={documentPage}
          onClose={() => setDocumentId(null)}
        />
      )}
      {switching && (
        <Modal
          title="Switch demonstration account"
          description="Each role signs in through the backend. Permissions remain enforced."
          onClose={() => setSwitching(false)}
        >
          <LoginChoices onLogin={signedIn} />
        </Modal>
      )}
      {toastNode}
    </div>
  );
}
