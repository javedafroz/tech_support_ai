import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { authHeaders } from "../auth";
import Badge from "../components/Badge";
import Drawer from "../components/Drawer";
import EmptyState from "../components/EmptyState";
import KpiCard from "../components/KpiCard";
import PageHeader from "../components/PageHeader";
import Skeleton from "../components/Skeleton";

type HandbookBreakdown = {
  document_id: string | null;
  title: string;
  resolved: number;
  escalated: number;
};

type Summary = {
  total_conversations: number;
  total_messages: number;
  tickets_created: number;
  deflections_resolved: number;
  deflections_escalated: number;
  deflection_rate: number;
  by_handbook: HandbookBreakdown[];
};

type TrendDay = {
  date: string;
  conversations: number;
  resolved: number;
  escalated: number;
};

type SessionItem = {
  id: string;
  user_id: string;
  org_id: string | null;
  status: string;
  active_ticket_number: string | null;
  message_count: number;
  deflection_outcome: string | null;
  deflection_steps_count: number | null;
  handbook_document_id: string | null;
  handbook_title: string | null;
  created_at: string;
  updated_at: string;
};

type SessionList = {
  items: SessionItem[];
  total: number;
};

type TranscriptMessage = {
  id: string;
  role: string;
  content: string | null;
  card: Record<string, unknown> | null;
  created_at: string;
};

const PAGE_SIZE = 20;
const CHART_COLORS = {
  conversations: "#2563eb",
  resolved: "#15803d",
  escalated: "#c2410c",
  none: "#94a3b8",
};

type PeriodPreset = "1d" | "7d" | "30d" | "custom";

function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function rangeForPreset(preset: PeriodPreset): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  if (preset === "1d") {
    // last 1 day = today only
  } else if (preset === "7d") {
    start.setDate(end.getDate() - 6);
  } else if (preset === "30d") {
    start.setDate(end.getDate() - 29);
  }
  return { start: toIsoDate(start), end: toIsoDate(end) };
}

function formatPercent(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

function formatCurrency(n: number): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const sec = Math.round((now - then) / 1000);
  if (sec < 60) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${day}d ago`;
  return new Date(iso).toLocaleDateString();
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function outcomeBadge(outcome: string | null) {
  if (!outcome) return <Badge variant="neutral">none</Badge>;
  if (outcome === "resolved") return <Badge variant="success">resolved</Badge>;
  if (outcome === "escalated") return <Badge variant="warning">escalated</Badge>;
  return <Badge>{outcome}</Badge>;
}

function IconChat() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function IconTicket() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4V9z" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}

function IconAlert() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v4M12 16h.01" />
    </svg>
  );
}

export default function DashboardTab() {
  const initialRange = rangeForPreset("30d");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [trends, setTrends] = useState<TrendDay[]>([]);
  const [sessions, setSessions] = useState<SessionList | null>(null);
  const [offset, setOffset] = useState(0);
  const [costPerTicket, setCostPerTicket] = useState(25);
  const [drawerSession, setDrawerSession] = useState<SessionItem | null>(null);
  const [transcript, setTranscript] = useState<TranscriptMessage[] | null>(null);
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const [period, setPeriod] = useState<PeriodPreset>("30d");
  const [startDate, setStartDate] = useState(initialRange.start);
  const [endDate, setEndDate] = useState(initialRange.end);
  const [customStart, setCustomStart] = useState(initialRange.start);
  const [customEnd, setCustomEnd] = useState(initialRange.end);

  const load = useCallback(
    async (nextOffset: number, rangeStart: string, rangeEnd: string) => {
      setLoading(true);
      setError(null);
      try {
        if (rangeEnd < rangeStart) {
          throw new Error("End date must be on or after start date");
        }
        const headers = await authHeaders();
        const qs = `start_date=${rangeStart}&end_date=${rangeEnd}`;
        const [summaryRes, trendsRes, sessionsRes] = await Promise.all([
          fetch(`/api/v1/admin/analytics/summary?${qs}`, { headers }),
          fetch(`/api/v1/admin/analytics/trends?${qs}`, { headers }),
          fetch(
            `/api/v1/admin/analytics/sessions?limit=${PAGE_SIZE}&offset=${nextOffset}&${qs}`,
            { headers },
          ),
        ]);
        if (!summaryRes.ok) {
          throw new Error(`/summary failed: ${summaryRes.status} ${await summaryRes.text()}`);
        }
        if (!trendsRes.ok) {
          throw new Error(`/trends failed: ${trendsRes.status} ${await trendsRes.text()}`);
        }
        if (!sessionsRes.ok) {
          throw new Error(`/sessions failed: ${sessionsRes.status} ${await sessionsRes.text()}`);
        }
        setSummary((await summaryRes.json()) as Summary);
        const trendsBody = (await trendsRes.json()) as { items: TrendDay[] };
        setTrends(trendsBody.items);
        setSessions((await sessionsRes.json()) as SessionList);
        setOffset(nextOffset);
        setStartDate(rangeStart);
        setEndDate(rangeEnd);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void load(0, startDate, endDate);
    // Initial load only; period changes call load explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function applyPreset(next: PeriodPreset) {
    setPeriod(next);
    if (next === "custom") {
      setCustomStart(startDate);
      setCustomEnd(endDate);
      return;
    }
    const range = rangeForPreset(next);
    void load(0, range.start, range.end);
  }

  function applyCustomRange() {
    setPeriod("custom");
    void load(0, customStart, customEnd);
  }

  async function openTranscript(session: SessionItem) {
    setDrawerSession(session);
    setTranscript(null);
    setTranscriptLoading(true);
    setError(null);
    try {
      const headers = await authHeaders();
      const res = await fetch(`/api/v1/admin/analytics/sessions/${session.id}/messages`, { headers });
      if (!res.ok) throw new Error(`Transcript failed: ${res.status} ${await res.text()}`);
      const data = (await res.json()) as { messages: TranscriptMessage[] };
      setTranscript(data.messages);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setDrawerSession(null);
    } finally {
      setTranscriptLoading(false);
    }
  }

  const estimatedSavings = summary ? summary.deflections_resolved * costPerTicket : 0;
  const pageEnd = sessions ? Math.min(offset + sessions.items.length, sessions.total) : 0;

  const chartData = useMemo(
    () =>
      trends.map((t) => ({
        ...t,
        label: shortDate(t.date),
      })),
    [trends],
  );

  const donutData = useMemo(() => {
    if (!summary) return [];
    const withOutcome = summary.deflections_resolved + summary.deflections_escalated;
    const none = Math.max(0, summary.total_conversations - withOutcome);
    return [
      { name: "Resolved", value: summary.deflections_resolved, color: CHART_COLORS.resolved },
      { name: "Escalated", value: summary.deflections_escalated, color: CHART_COLORS.escalated },
      { name: "No L1 attempt", value: none, color: CHART_COLORS.none },
    ].filter((d) => d.value > 0);
  }, [summary]);

  const handbookMax = useMemo(() => {
    if (!summary?.by_handbook.length) return 1;
    return Math.max(
      1,
      ...summary.by_handbook.map((h) => h.resolved + h.escalated),
    );
  }, [summary]);

  return (
    <>
      {loading ? <div className="top-progress" aria-hidden="true"><span /></div> : null}

      <PageHeader
        title="Dashboard"
        subtitle="Conversation volume, L1 deflection outcomes, and estimated ticket savings."
        actions={
          <div className="period-controls">
            <label className="period-label" htmlFor="period-select">
              Period
            </label>
            <select
              id="period-select"
              className="select period-select"
              value={period}
              onChange={(e) => applyPreset(e.target.value as PeriodPreset)}
              disabled={loading}
            >
              <option value="1d">Last 1 day</option>
              <option value="7d">Last 1 week</option>
              <option value="30d">Last 1 month</option>
              <option value="custom">Custom dates</option>
            </select>
            {period === "custom" ? (
              <div className="period-custom">
                <input
                  type="date"
                  className="input"
                  value={customStart}
                  max={customEnd}
                  onChange={(e) => setCustomStart(e.target.value)}
                  aria-label="Start date"
                />
                <span className="muted">to</span>
                <input
                  type="date"
                  className="input"
                  value={customEnd}
                  min={customStart}
                  onChange={(e) => setCustomEnd(e.target.value)}
                  aria-label="End date"
                />
                <button
                  className="btn secondary sm"
                  type="button"
                  disabled={loading || !customStart || !customEnd}
                  onClick={applyCustomRange}
                >
                  Apply
                </button>
              </div>
            ) : null}
            <button
              className="btn secondary"
              type="button"
              onClick={() => void load(offset, startDate, endDate)}
              disabled={loading}
            >
              Refresh
            </button>
          </div>
        }
      />

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="kpi-grid">
        <KpiCard
          loading={loading && !summary}
          label="Conversations"
          value={summary?.total_conversations ?? "—"}
          caption={summary ? `${summary.total_messages} messages` : undefined}
          icon={<IconChat />}
        />
        <KpiCard
          loading={loading && !summary}
          label="Tickets created"
          value={summary?.tickets_created ?? "—"}
          caption="Sessions with a ticket number"
          icon={<IconTicket />}
        />
        <KpiCard
          loading={loading && !summary}
          label="Deflected"
          value={summary?.deflections_resolved ?? "—"}
          caption="Resolved without a ticket"
          icon={<IconCheck />}
          iconTone="success"
        />
        <KpiCard
          loading={loading && !summary}
          label="Escalated after L1"
          value={summary?.deflections_escalated ?? "—"}
          caption="Troubleshoot then ticketed"
          icon={<IconAlert />}
          iconTone="warning"
        />
        <KpiCard
          loading={loading && !summary}
          label="Deflection rate"
          value={summary ? formatPercent(summary.deflection_rate) : "—"}
          caption="Resolved ÷ (resolved + escalated)"
          progress={summary?.deflection_rate}
        />
        <KpiCard
          loading={loading && !summary}
          label="Est. savings"
          value={<span className="roi-highlight">{formatCurrency(estimatedSavings)}</span>}
          caption={
            <span className="row">
              <label htmlFor="cost-per-ticket">$/ticket</label>
              <input
                id="cost-per-ticket"
                type="number"
                min={0}
                step={1}
                value={costPerTicket}
                onChange={(e) => setCostPerTicket(Number(e.target.value) || 0)}
                className="cost-input"
              />
            </span>
          }
        />
      </div>

      <div className="chart-grid">
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">
              Activity ({startDate === endDate ? startDate : `${startDate} → ${endDate}`})
            </h2>
          </div>
          <div className="card-body">
            {loading && !trends.length ? (
              <Skeleton height={240} />
            ) : chartData.every((d) => !d.conversations && !d.resolved && !d.escalated) ? (
              <EmptyState title="No activity yet" description="Trends appear once conversations start flowing." />
            ) : (
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="fillConv" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={CHART_COLORS.conversations} stopOpacity={0.25} />
                        <stop offset="100%" stopColor={CHART_COLORS.conversations} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#64748b" }} interval="preserveStartEnd" />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#64748b" }} width={32} />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 8,
                        border: "1px solid #e2e8f0",
                        fontSize: 12,
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Area
                      type="monotone"
                      dataKey="conversations"
                      name="Conversations"
                      stroke={CHART_COLORS.conversations}
                      fill="url(#fillConv)"
                      strokeWidth={2}
                    />
                    <Area
                      type="monotone"
                      dataKey="resolved"
                      name="Resolved"
                      stroke={CHART_COLORS.resolved}
                      fill="transparent"
                      strokeWidth={2}
                    />
                    <Area
                      type="monotone"
                      dataKey="escalated"
                      name="Escalated"
                      stroke={CHART_COLORS.escalated}
                      fill="transparent"
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </section>

        <section className="card">
          <div className="card-header">
            <h2 className="card-title">Outcomes</h2>
          </div>
          <div className="card-body">
            {loading && !summary ? (
              <Skeleton height={240} />
            ) : donutData.length === 0 ? (
              <EmptyState title="No outcomes yet" description="Deflection outcomes will show here." />
            ) : (
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={donutData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={58}
                      outerRadius={88}
                      paddingAngle={2}
                    >
                      {donutData.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        borderRadius: 8,
                        border: "1px solid #e2e8f0",
                        fontSize: 12,
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">By handbook</h2>
        </div>
        <div className="card-body flush">
          {!summary || summary.by_handbook.length === 0 ? (
            <EmptyState
              title="No handbook activity"
              description="When L1 troubleshooting runs, outcomes are grouped by handbook here."
            />
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Handbook</th>
                    <th>Resolved</th>
                    <th>Escalated</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.by_handbook.map((row) => {
                    const total = row.resolved + row.escalated;
                    return (
                      <tr key={row.document_id ?? row.title}>
                        <td>{row.title}</td>
                        <td>
                          <div className="bar-cell">
                            <div className="bar-track">
                              <div
                                className="bar-fill success"
                                style={{ width: `${(row.resolved / handbookMax) * 100}%` }}
                              />
                            </div>
                            <span className="bar-num">{row.resolved}</span>
                          </div>
                        </td>
                        <td>
                          <div className="bar-cell">
                            <div className="bar-track">
                              <div
                                className="bar-fill warning"
                                style={{ width: `${(row.escalated / handbookMax) * 100}%` }}
                              />
                            </div>
                            <span className="bar-num">{row.escalated}</span>
                          </div>
                        </td>
                        <td>{total}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">Conversations</h2>
        </div>
        <div className="card-body flush">
          {!sessions || sessions.total === 0 ? (
            <EmptyState title="No conversations yet" description="Chat sessions will appear here as users engage." />
          ) : (
            <>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Updated</th>
                      <th>User</th>
                      <th>Messages</th>
                      <th>Outcome</th>
                      <th>Handbook</th>
                      <th>Ticket</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.items.map((s) => (
                      <tr key={s.id}>
                        <td title={formatDate(s.updated_at)}>{formatRelative(s.updated_at)}</td>
                        <td>{s.user_id}</td>
                        <td>{s.message_count}</td>
                        <td>{outcomeBadge(s.deflection_outcome)}</td>
                        <td className="muted">{s.handbook_title ?? "—"}</td>
                        <td>{s.active_ticket_number ? <Badge variant="info">{s.active_ticket_number}</Badge> : "—"}</td>
                        <td>
                          <button className="btn secondary sm" type="button" onClick={() => void openTranscript(s)}>
                            Transcript
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="table-footer">
                <span>
                  Showing {sessions.items.length === 0 ? 0 : offset + 1}–{pageEnd} of {sessions.total}
                </span>
                <div className="row">
                  <button
                    className="btn secondary sm"
                    type="button"
                    disabled={loading || offset === 0}
                    onClick={() => void load(Math.max(0, offset - PAGE_SIZE), startDate, endDate)}
                  >
                    Previous
                  </button>
                  <button
                    className="btn secondary sm"
                    type="button"
                    disabled={loading || pageEnd >= sessions.total}
                    onClick={() => void load(offset + PAGE_SIZE, startDate, endDate)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </section>

      <Drawer
        open={Boolean(drawerSession)}
        title="Conversation transcript"
        subtitle={
          drawerSession
            ? `${drawerSession.user_id} · ${formatDate(drawerSession.updated_at)}`
            : undefined
        }
        onClose={() => {
          setDrawerSession(null);
          setTranscript(null);
        }}
      >
        {transcriptLoading ? (
          <div className="row" style={{ justifyContent: "center", padding: "2rem" }}>
            <span className="spinner" />
          </div>
        ) : transcript && transcript.length === 0 ? (
          <EmptyState title="Empty session" description="No messages recorded for this conversation." />
        ) : (
          <div className="transcript">
            {(transcript ?? []).map((m) => (
              <div key={m.id} className={`bubble ${m.role}`}>
                <div className="bubble-meta">
                  <strong>{m.role}</strong>
                  <span className="muted">{formatDate(m.created_at)}</span>
                </div>
                <div className="bubble-body">
                  {m.content || (m.card ? JSON.stringify(m.card, null, 2) : "(empty)")}
                </div>
              </div>
            ))}
          </div>
        )}
      </Drawer>
    </>
  );
}
