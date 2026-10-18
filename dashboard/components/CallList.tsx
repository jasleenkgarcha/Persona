"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import Icon from "@/components/Icon";
import Mascot from "@/components/Mascot";
import { callerTitle, formatClock, formatDay, formatPhone, previewLine } from "@/lib/format";
import { CHALLENGE_LABEL, decisionLabel, STATUS_LABEL } from "@/lib/labels";
import type { Call, Status, Verdict } from "@/lib/types";
import { useCalls } from "@/lib/use-calls";

type Filter = "all" | Verdict | "pending" | "failed";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "scam", label: "Scam" },
  { id: "legit", label: "Legit" },
  { id: "unsure", label: "Unsure" },
  { id: "pending", label: "Pending" },
  { id: "failed", label: "Failed" },
];

function matches(call: Call, filter: Filter): boolean {
  if (filter === "all") return true;
  if (filter === "pending" || filter === "failed") return call.status === filter;
  return call.verdict === filter;
}

function rowTone(call: Call): string {
  if (call.status === "pending") return "pending";
  if (call.status === "failed") return "failed";
  return call.verdict ?? "unsure";
}

export default function CallList() {
  const { calls, source, error } = useCalls();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    if (!calls) return [];
    const needle = query.trim().toLowerCase();
    return calls.filter((call) => {
      if (!matches(call, filter)) return false;
      if (!needle) return true;
      const haystack = `${callerTitle(call)} ${call.caller_number ?? ""} ${previewLine(call)}`.toLowerCase();
      return haystack.includes(needle);
    });
  }, [calls, filter, query]);

  const all = calls ?? [];
  const blocked = all.filter((call) => call.mid_call_decision === "block").length;
  const passed = all.filter((call) => call.mid_call_decision === "pass").length;
  const open = all.filter((call) => call.status !== "scored").length;

  return (
    <main>
      <section className="stage">
        <div className="stage-copy">
          <div className="active-sticker">
            <span className="pulse" /> Screening is live
          </div>
          <h1>
            A little <span>proof</span>
            <br />
            before hello.
          </h1>
          <p>
            Unknown caller? We ask one question, watch how they react, and only ring Ian when the
            story checks out.
          </p>
        </div>
        <aside className="stage-card">
          <Mascot tone="on-dark" className="stage-mascot" />
          <ol>
            <li>
              <span>01</span>
              <div>
                <b>Ask</b>
                <small>Name and reason</small>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <b>Test</b>
                <small>Official callback, or the safe word</small>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <b>Decide</b>
                <small>Pass to Ian, or block</small>
              </div>
            </li>
          </ol>
        </aside>
      </section>

      <section className="metrics" aria-label="Summary">
        <div className="metric">
          <div className="metric-label">
            <Icon name="shield" size={16} /> On the desk
          </div>
          <strong>{all.length}</strong>
          <span>{source === "live" ? "Live from Supabase" : "Sample calls"}</span>
        </div>
        <div className="metric">
          <div className="metric-label">
            <Icon name="phone-block" size={16} /> Blocked
          </div>
          <strong>{blocked}</strong>
          <span className="metric-note">Stopped before Ian</span>
        </div>
        <div className="metric">
          <div className="metric-label">
            <Icon name="phone-pass" size={16} /> Passed to Ian
          </div>
          <strong>{passed}</strong>
          <span className="metric-note">The story checked out</span>
        </div>
        <div className="metric">
          <div className="metric-label">
            <Icon name="phone-wait" size={16} /> Still open
          </div>
          <strong>{open}</strong>
          <span className="metric-note">Pending or failed</span>
        </div>
      </section>

      {error && <p className="banner banner-hot">{error}</p>}

      <section className="calls-section">
        <div className="section-heading">
          <h2>
            Recent calls <span>{visible.length}</span>
          </h2>
        </div>
        <div className="toolbar">
          <div className="filters" role="group" aria-label="Filter calls">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={filter === item.id ? "active" : ""}
                onClick={() => setFilter(item.id)}
              >
                {item.label}
                {item.id !== "all" && (
                  <span>{all.filter((call) => matches(call, item.id)).length}</span>
                )}
              </button>
            ))}
          </div>
          <label className="search">
            <Icon name="search" size={16} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search calls"
            />
          </label>
        </div>

        {calls === null ? (
          <div className="stack" aria-hidden="true">
            <div className="skeleton" />
            <div className="skeleton" />
          </div>
        ) : visible.length === 0 ? (
          <EmptyDesk
            filtered={filter !== "all" || query.trim().length > 0}
            onReset={() => {
              setFilter("all");
              setQuery("");
            }}
          />
        ) : (
          <div className="call-table">
            <div className="table-header">
              <span>Time / caller</span>
              <span>What happened</span>
              <span>Verdict</span>
              <span>Scam score</span>
              <span>Decision</span>
              <span />
            </div>
            {visible.map((call) => (
              <CallRow key={call.conversation_id} call={call} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function CallRow({ call }: { call: Call }) {
  const decision = decisionLabel(call.mid_call_decision);
  const tone = rowTone(call);
  return (
    <Link href={`/calls/${call.conversation_id}`} className={`call-row row-${tone}`}>
      <span className="caller-cell">
        <span className="caller-mark" aria-hidden="true">
          <Icon name="phone" size={16} />
        </span>
        <span className="caller-copy">
          <span className="time">
            <time dateTime={call.created_at}>{formatClock(call.created_at)}</time>{" "}
            <small>{formatDay(call.created_at)}</small>
          </span>
          <strong>{callerTitle(call)}</strong>
          <small>{formatPhone(call.caller_number)}</small>
        </span>
      </span>
      <span className="summary-cell">
        <span>{previewLine(call)}</span>
        <span className="evidence-tags">
          {call.challenge_response && (
            <em className={call.challenge_response === "accepted" || call.challenge_response === "safe_word_passed" ? "positive" : ""}>
              {CHALLENGE_LABEL[call.challenge_response]}
            </em>
          )}
          {call.pressure_after_challenge && <em>Pressure after challenge</em>}
          {call.status !== "scored" && <em className="quiet">{STATUS_LABEL[call.status as Status]}</em>}
        </span>
      </span>
      <span>
        <VerdictPill verdict={call.verdict} status={call.status} />
      </span>
      <span className="score-cell">
        {call.scam_score != null ? (
          <>
            <b>{call.scam_score}</b>
            <small>/100</small>
            <i>
              <u className={call.verdict ?? "none"} style={{ width: `${call.scam_score}%` }} />
            </i>
          </>
        ) : (
          <>
            <b className="dash">—</b>
            <small>{STATUS_LABEL[call.status]}</small>
          </>
        )}
      </span>
      <span className="decision-cell">
        <b className={call.mid_call_decision === "pass" ? "passed" : decision ? "" : "open"}>
          {decision ?? "Waiting"}
        </b>
        <small>{STATUS_LABEL[call.status]}</small>
      </span>
      <span className="row-arrow">
        <Icon name="chevron" size={18} />
      </span>
    </Link>
  );
}

function VerdictPill({ verdict, status }: { verdict: Verdict | null; status: Status }) {
  if (status === "pending") return <span className="verdict verdict-pending">Pending</span>;
  if (status === "failed" && !verdict) return <span className="verdict verdict-failed">Failed</span>;
  if (!verdict) return <span className="verdict verdict-failed">No verdict</span>;
  const label = verdict === "scam" ? "Scam" : verdict === "legit" ? "Legit" : "Unsure";
  return <span className={`verdict verdict-${verdict}`}>{label}</span>;
}

function EmptyDesk({ filtered, onReset }: { filtered: boolean; onReset: () => void }) {
  return (
    <div className="empty-state">
      {filtered ? (
        <div className="empty-art">
          <Icon name="search" size={26} />
        </div>
      ) : (
        <Mascot tone="on-light" className="empty-mascot" />
      )}
      <h3>{filtered ? "No calls found" : "Quiet on the line"}</h3>
      <p>
        {filtered
          ? "Try another verdict or clear the search to see the calls again."
          : "New screened calls show up here, with the test that shaped each decision."}
      </p>
      {filtered && (
        <button type="button" onClick={onReset}>
          Clear filters
        </button>
      )}
    </div>
  );
}
