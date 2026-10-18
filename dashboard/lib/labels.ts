import type { ChallengeResponse, Decision, Status, Verdict } from "./types";

export const CHALLENGE_LABEL: Record<ChallengeResponse, string> = {
  accepted: "Accepted callback",
  refused: "Refused callback",
  evaded: "Evaded challenge",
  safe_word_passed: "Safe word passed",
  safe_word_failed: "Safe word failed",
};

export const VERDICT_LABEL: Record<Verdict, string> = {
  scam: "Scam",
  legit: "Legit",
  unsure: "Unsure",
};

export const STATUS_LABEL: Record<Status, string> = {
  pending: "Pending",
  scored: "Scored",
  failed: "Failed",
};

export function decisionLabel(decision: Decision | null): string | null {
  if (decision === "pass") return "Passed to Ian";
  if (decision === "block") return "Blocked";
  return null;
}

export function tacticLabel(tactic: string): string {
  return tactic.replaceAll("_", " ");
}

const HARSH_RESPONSES = new Set<ChallengeResponse>([
  "refused",
  "evaded",
  "safe_word_failed",
]);

export function challengeTone(
  response: ChallengeResponse | null,
): "calm" | "hot" | "quiet" {
  if (!response) return "quiet";
  return HARSH_RESPONSES.has(response) ? "hot" : "calm";
}
