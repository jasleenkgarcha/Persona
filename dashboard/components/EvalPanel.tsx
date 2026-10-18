"use client";

import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import Mascot from "@/components/Mascot";
import { formatRunAt, percent, percentPoints } from "@/lib/format";
import type { EvalMiss, EvalResults } from "@/lib/types";

export default function EvalPanel() {
  const [results, setResults] = useState<EvalResults | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch("/eval-results.json", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Eval file missing");
        return (await response.json()) as EvalResults;
      })
      .then((data) => {
        if (active) setResults(data);
      })
      .catch(() => {
        if (active) setError("eval-results.json is not in dashboard/public yet.");
      });
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <main className="evaluation-page">
        <section className="evaluation-hero">
          <h1>The comparison is not in yet.</h1>
          <p>{error}</p>
        </section>
      </main>
    );
  }

  if (!results) {
    return (
      <main className="evaluation-page">
        <p>Loading eval results…</p>
      </main>
    );
  }

  const listen = results.listen_only;
  const tested = results.test_the_caller;
  const rows = [
    {
      label: "Accuracy",
      listen: percent(listen?.accuracy),
      test: percent(tested?.accuracy),
      note: signed(gap(listen?.accuracy, tested?.accuracy)),
      listenWidth: percentPoints(listen?.accuracy),
      testWidth: percentPoints(tested?.accuracy),
    },
    {
      label: "Missed scams",
      listen: percent(listen?.false_negative_rate),
      test: percent(tested?.false_negative_rate),
      note: fewer(gap(tested?.false_negative_rate, listen?.false_negative_rate)),
    },
    {
      label: "False flags",
      listen: percent(listen?.false_positive_rate),
      test: percent(tested?.false_positive_rate),
      note: fewer(gap(tested?.false_positive_rate, listen?.false_positive_rate)),
    },
  ];
  const misses = (tested?.misses ?? results.misses ?? []).slice(0, 2);

  return (
    <main className="evaluation-page">
      <header className="eval-head">
        <div>
          <p className="eyebrow">
            {results.sample ? "Sample run" : "Latest run"} · {results.n_total ?? tested?.n_total ?? "—"} calls
          </p>
          <h1>
            Listening helps.
            <br />
            <em>Testing proves.</em>
          </h1>
          <p>Same calls. One extra question, scored on how the caller reacts.</p>
        </div>
        <div className="eval-mark">
          <Mascot tone="on-dark" className="stage-mascot" />
        </div>
      </header>

      <section className="comparison">
        <div className="comparison-head">
          <div>
            <span>Approach</span>
            <b>What the system does</b>
          </div>
          <div className="listen-col">
            <span>Baseline</span>
            <b>Listen-only</b>
            <small>Words and tone</small>
          </div>
          <div className="test-col">
            <span>
              <Icon name="spark" size={13} /> goodcall
            </span>
            <b>Test the caller</b>
            <small>One safe verification step</small>
          </div>
          <div />
        </div>
        {rows.map((row) => (
          <div className="comparison-row" key={row.label}>
            <div>
              <b>{row.label}</b>
            </div>
            <div className="listen-col">
              <strong>{row.listen}</strong>
              {row.listenWidth != null && <i style={{ width: `${row.listenWidth}%` }} />}
            </div>
            <div className="test-col">
              <strong>{row.test}</strong>
              {row.testWidth != null && <i style={{ width: `${row.testWidth}%` }} />}
            </div>
            <div>
              <span className="improvement">{row.note}</span>
            </div>
          </div>
        ))}
      </section>

      <div className="illustrative-note">
        <Icon name="shield" size={15} />
        <span>
          <b>{results.sample ? "Sample numbers." : "Latest run."}</b>{" "}
          {results.model ?? "Model not set"} · flip rate {percent(results.flip_rate)} across 3 runs ·{" "}
          {formatRunAt(results.run_at)}
        </span>
      </div>

      <section className="misses">
        <div className="misses-heading">
          <h2>Misses</h2>
          <p>Calls this run still got wrong.</p>
        </div>
        {misses.length === 0 ? (
          <article>
            <p className="case-type">No misses recorded</p>
            <h3>This run did not list a miss.</h3>
          </article>
        ) : (
          misses.map((miss, index) => <MissCard key={miss.id ?? index} miss={miss} index={index} />)
        )}
      </section>
    </main>
  );
}

function MissCard({ miss, index }: { miss: EvalMiss; index: number }) {
  const expected = miss.expected ?? "—";
  const got = miss.got ?? "—";
  return (
    <article>
      <span className="case-number">{String(index + 1).padStart(2, "0")}</span>
      <div className={`case-icon${expected === "legit" ? " family" : ""}`}>
        <Icon name={expected === "legit" ? "lock" : "phone"} size={18} />
      </div>
      <p className="case-type">{expected === "scam" ? "Missed scam" : "False flag"}</p>
      <h3>{miss.id?.replaceAll("_", " ") ?? "Untitled miss"}</h3>
      <p>{miss.note ?? `Expected ${expected}, got ${got}.`}</p>
      <div className="case-footer">
        <span className={`verdict verdict-${got === "legit" || got === "scam" || got === "unsure" ? got : "failed"}`}>
          {got}
        </span>
        <span>Should be {expected}</span>
      </div>
    </article>
  );
}

function gap(from: number | undefined, to: number | undefined): number | null {
  const start = percentPoints(from);
  const end = percentPoints(to);
  if (start == null || end == null) return null;
  return end - start;
}

function signed(value: number | null): string {
  if (value == null) return "—";
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value} pts`;
}

function fewer(value: number | null): string {
  if (value == null) return "—";
  if (value === 0) return "Same";
  if (value > 0) return `${value} pts fewer`;
  return `${Math.abs(value)} pts more`;
}
