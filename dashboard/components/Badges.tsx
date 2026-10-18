import type { ChallengeResponse, Decision, Status, Verdict } from "@/lib/types";
import { challengeTone, CHALLENGE_LABEL, decisionLabel, STATUS_LABEL, VERDICT_LABEL } from "@/lib/labels";

export function VerdictBadge({ verdict }: { verdict: Verdict | null }) {
  if (!verdict) return <span className="badge badge-quiet">No verdict</span>;
  return <span className={`badge badge-${verdict}`}>{VERDICT_LABEL[verdict]}</span>;
}

export function DecisionBadge({ decision }: { decision: Decision | null }) {
  const label = decisionLabel(decision);
  if (!label) return null;
  return <span className={`badge badge-${decision}`}>{label}</span>;
}

export function ChallengeBadge({ response }: { response: ChallengeResponse | null }) {
  if (!response) return null;
  return (
    <span className={`badge badge-challenge badge-challenge-${challengeTone(response)}`}>
      {CHALLENGE_LABEL[response]}
    </span>
  );
}

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge badge-status badge-status-${status}`}>{STATUS_LABEL[status]}</span>;
}

export function PressureBadge({ pressure }: { pressure: boolean | null }) {
  if (!pressure) return null;
  return <span className="badge badge-pressure">Pressure after challenge</span>;
}
