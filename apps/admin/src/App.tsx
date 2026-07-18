import { useCallback, useEffect, useState } from "react";
import { authHeaders, initKeycloak, keycloak } from "./auth";
import ProfileMenu from "./components/ProfileMenu";
import ConfigurationTab, { type MeResponse } from "./tabs/ConfigurationTab";
import DashboardTab from "./tabs/DashboardTab";

type TabId = "dashboard" | "configuration";

function IconDashboard() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="3" width="8" height="8" rx="1.5" />
      <rect x="13" y="3" width="8" height="5" rx="1.5" />
      <rect x="13" y="10" width="8" height="11" rx="1.5" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" />
    </svg>
  );
}

function IconConfig() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
    </svg>
  );
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [tab, setTab] = useState<TabId>("dashboard");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const authenticated = await initKeycloak();
        if (!cancelled) {
          setReady(authenticated);
          if (!authenticated) setError("Keycloak authentication failed");
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const loadMe = useCallback(async () => {
    setError(null);
    try {
      const headers = await authHeaders();
      const meRes = await fetch("/api/v1/admin/kb/me", { headers });
      if (!meRes.ok) throw new Error(`/me failed: ${meRes.status} ${await meRes.text()}`);
      setMe((await meRes.json()) as MeResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    if (ready) void loadMe();
  }, [ready, loadMe]);

  if (!ready && !error) {
    return (
      <div className="boot-screen">
        <div className="boot-card">
          <span className="spinner" style={{ margin: "0 auto 1rem" }} />
          <p className="muted" style={{ margin: 0 }}>
            Signing in with Keycloak…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-logo">TS</div>
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-title">Tech Support AI</span>
            <span className="sidebar-brand-sub">Admin Console</span>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Admin sections">
          <button
            type="button"
            className={`nav-item ${tab === "dashboard" ? "active" : ""}`}
            onClick={() => setTab("dashboard")}
          >
            <IconDashboard />
            <span>Dashboard</span>
          </button>
          <button
            type="button"
            className={`nav-item ${tab === "configuration" ? "active" : ""}`}
            onClick={() => setTab("configuration")}
          >
            <IconConfig />
            <span>Configuration</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <ProfileMenu
            me={me}
            onSignOut={() => void keycloak.logout({ redirectUri: window.location.origin })}
          />
        </div>
      </aside>

      <main className="content">
        <div className="content-inner">
          {error ? <div className="error-banner">{error}</div> : null}
          {tab === "dashboard" ? <DashboardTab /> : <ConfigurationTab me={me} />}
        </div>
      </main>
    </div>
  );
}
