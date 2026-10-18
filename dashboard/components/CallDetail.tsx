"use client";

import Link from "next/link";
import { type ReactNode } from "react";
import Icon from "@/components/Icon";
import {
  asStrings,
  asTranscript,
  callerTitle,
  challengeTurnIndex,
  formatClock,
  formatPhone,
} from "@/lib/format";
import { CHALLENGE_LABEL, decisionLabel, STATUS_LABEL, tacticLabel, VERDICT_LABEL } from "@/lib/labels";
import type { Call, Status, Turn, Verdict } from "@/lib/types";
import { useCalls } from "@/lib/use-calls";

export default function CallDetail({ id }: { id: string }) {
  const { calls, error } = useCalls();
  const call = calls?.find((item) => item.conversation_id === id) ?? null;

  if (calls === null) {
    return (
      <main className="detail-page">
        <p className="hero-copy">Loading this call…</p>
      </main>
    );
  }

  if (!call) {
    return (
      <main className="detail-page">
        <Link href="/" className="back-button">
          <span>←</span> Back to calls
        </Link>
        <h1>This call is not on the desk.</h1>
        {error && <p className="banner banner-hot">{error}</p>}
      </main>
    );
  }

  const decision = decisionLabel(call.mid_call_decision);

  return (
    <main className="detail-page">
      <Link href="/" className="back-button">
        <span>←</span> Back to calls
      </Link>
      <section className="detail-title">
        <div>
          <p className="eyebrow">Screened at {formatClock(call.created_at)}</p>
          <h1>{callerTitle(call)}</h1>
          <p>{formatPhone(call.caller_number)}</p>
        </div>
        <div className="title-verdict">
          <VerdictPill verdict={call.verdict} status={call.status} />
          <b>{decision ?? STATUS_LABEL[call.status]}</b>
        </div>
      </section>
      <div className="detail-grid">
        <Transcript call={call} />
        <Dossier call={call} />
      </div>
    </main>
  );
}

function Transcript({ call }: { call: Call }) {
  const turns = asTranscript(call.transcript);
  const testAt = challengeTurnIndex(call);

  return (
    <section className="conversation-card">
      <div className="card-head">
        <div>
          <span className="live-dot" /> Screening transcript
        </div>
        <span className="turn-count">{turns.length} turns</span>
      </div>
      {turns.length === 0 ? (
        <div className="empty-state empty-inline">
          <h3>No turns yet</h3>
          <p>The transcript fills in as the call goes, and again when the post-call webhook lands.</p>
        </div>
      ) : (
        <div className="transcript">
          {renderTurns(turns, testAt, call)}
        </div>
      )}
    </section>
  );
}

function renderTurns(turns: Turn[], testAt: number, call: Call): ReactNode[] {
  const blocks: ReactNode[] = [];
  let index = 0;
  while (index < turns.length) {
    if (index === testAt) {
      const reaction = turns[index + 1]?.role === "caller" ? turns[index + 1] : null;
      blocks.push(
        <div key={`test-${index}`}>
          <div className="challenge-label">
            <span>Verification test</span>
          </div>
          <Bubble turn={turns[index]} testing />
          {reaction && (
            <div className="reaction">
              <div className="reaction-head">
                <span>Caller reaction</span>
                <b>{call.challenge_response ? CHALLENGE_LABEL[call.challenge_response] : "Not labeled"}</b>
              </div>
              <Bubble turn={reaction} />
              <div className="reaction-signals">
                {call.challenge_response && <span>{CHALLENGE_LABEL[call.challenge_response]}</span>}
                {call.pressure_after_challenge && <span>Pressure after challenge</span>}
              </div>
            </div>
          )}
        </div>,
      );
      index += reaction ? 2 : 1;
      continue;
    }
    blocks.push(<Bubble key={index} turn={turns[index]} />);
    index += 1;
  }
  return blocks;
}

function Bubble({ turn, testing }: { turn: Turn; testing?: boolean }) {
  const agent = turn.role === "agent";
  return (
    <div className={`chat ${agent ? "agent" : "caller"}${testing ? " test-chat" : ""}`}>
      {agent && (
        <span className="chat-avatar">
          <Icon name={testing ? "shield" : "spark"} size={14} />
        </span>
      )}
      <div>
        <small>{agent ? "goodcall agent" : "Caller"}</small>
        <p>{turn.text}</p>
      </div>
    </div>
  );
}

function Dossier({ call }: { call: Call }) {
  const reasons = asStrings(call.reasons);
  const tactics = asStrings(call.tactics);
  const decision = decisionLabel(call.mid_call_decision);
  const score = call.scam_score ?? 0;
  const headline =
    call.verdict === "scam"
      ? "Very likely a scam"
      : call.verdict
        ? VERDICT_LABEL[call.verdict]
        : STATUS_LABEL[call.status];

  return (
    <aside className="detail-aside">
      <section className={`score-card tone-${call.verdict ?? call.status}`}>
        <div
          className="score-ring"
          style={{ ["--score" as string]: `${call.scam_score == null ? 0 : score}%` }}
        >
          <div>
            <strong>{call.scam_score ?? "—"}</strong>
            <span>/100</span>
          </div>
        </div>
        <div>
          <p>Scam score</p>
          <h3>{headline}</h3>
          <span>{decision ?? "Not decided yet"}</span>
        </div>
      </section>

      {call.status === "pending" && (
        <p className="banner">Still scoring. The verdict lands here when the scorer returns.</p>
      )}
      {call.status === "failed" && (
        <p className="banner banner-hot">The scorer did not finish. This call needs a person.</p>
      )}

      <section className="insight-card">
        <div className="card-title">
          <span>
            <Icon name="shield" size={16} />
          </span>
          Why this decision
        </div>
        <div className="insight-block">
          <small>Question tested</small>
          <p>{call.challenge_asked ?? "The challenge has not been recorded on this call."}</p>
        </div>
        <div className="insight-block">
          <small>Strongest reasons</small>
          {reasons.length === 0 ? (
            <p className="muted">None yet.</p>
          ) : (
            <ul>
              {reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}
        </div>
        <div className="tactics">
          <small>Tactics detected</small>
          {tactics.length === 0 ? (
            <span>None flagged</span>
          ) : (
            tactics.map((tactic) => <span key={tactic}>{tacticLabel(tactic)}</span>)
          )}
        </div>
      </section>

      <section className="summary-card">
        <p className="eyebrow">In one sentence</p>
        <h3>{call.summary ?? "No summary yet."}</h3>
      </section>

      <section className="sms-card">
        <div className="card-title">
          <span>
            <Icon name="message" size={16} />
          </span>
          Text to Ian
        </div>
        <div className="sms-bubble">
          <b>goodcall</b>
          <p>
            {decision ?? "Holding"} a call from {formatPhone(call.caller_number)}
            {call.scam_score != null ? ` (${call.scam_score}/100)` : ""}.{" "}
            {call.summary ?? "Review it on the desk."}
          </p>
          <small>{call.imessage_sent ? "Sent" : "Not sent yet"}</small>
        </div>
      </section>
    </aside>
  );
}

function VerdictPill({ verdict, status }: { verdict: Verdict | null; status: Status }) {
  if (!verdict && status === "pending") return <span className="verdict verdict-pending">Pending</span>;
  if (!verdict) return <span className="verdict verdict-failed">Failed</span>;
  return <span className={`verdict verdict-${verdict}`}>{VERDICT_LABEL[verdict]}</span>;
}
