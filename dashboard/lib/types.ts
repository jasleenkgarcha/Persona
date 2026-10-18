export type Role = "agent" | "caller";

export type Turn = {
  role: Role;
  text: string;
};

export type Verdict = "scam" | "legit" | "unsure";
export type Decision = "pass" | "block";
export type Status = "pending" | "scored" | "failed";

export type ChallengeResponse =
  | "accepted"
  | "refused"
  | "evaded"
  | "safe_word_passed"
  | "safe_word_failed";

export type Call = {
  conversation_id: string;
  created_at: string;
  caller_number: string | null;
  transcript: Turn[] | null;
  mid_call_decision: Decision | null;
  verdict: Verdict | null;
  scam_score: number | null;
  reasons: unknown;
  tactics: unknown;
  summary: string | null;
  challenge_asked: string | null;
  challenge_response: ChallengeResponse | null;
  pressure_after_challenge: boolean | null;
  status: Status;
  imessage_sent: boolean;
};

export type EvalMiss = {
  id?: string;
  expected?: string;
  got?: string;
  note?: string;
};

export type EvalBlock = {
  n_total?: number;
  accuracy?: number;
  false_positive_rate?: number;
  false_negative_rate?: number;
  misses?: EvalMiss[];
};

export type EvalResults = {
  sample?: boolean;
  run_at?: string;
  model?: string;
  n_total?: number;
  accuracy?: number;
  false_positive_rate?: number;
  false_negative_rate?: number;
  misses?: EvalMiss[];
  flip_rate?: number;
  listen_only?: EvalBlock;
  test_the_caller?: EvalBlock;
};

export type DeskSource = "loading" | "mock" | "live" | "error";
