"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { normalizeCall, sortCalls } from "./format";
import { MOCK_CALLS } from "./mock-calls";
import { getSupabase, isLiveConfigured } from "./supabase";
import type { Call, DeskSource } from "./types";

type CallsState = {
  calls: Call[] | null;
  source: DeskSource;
  error: string | null;
};

const CallsContext = createContext<CallsState>({
  calls: null,
  source: "loading",
  error: null,
});

function applyRow(current: Call[], next: Call): Call[] {
  return sortCalls([
    normalizeCall(next),
    ...current.filter((call) => call.conversation_id !== next.conversation_id),
  ]);
}

export function CallsProvider({ children }: { children: React.ReactNode }) {
  const configured = isLiveConfigured();
  const [calls, setCalls] = useState<Call[] | null>(configured ? null : MOCK_CALLS);
  const [source, setSource] = useState<DeskSource>(configured ? "loading" : "mock");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) return;

    let active = true;

    supabase
      .from("calls")
      .select("*")
      .order("created_at", { ascending: false })
      .then(({ data, error: loadError }) => {
        if (!active) return;
        if (loadError) {
          setError(loadError.message);
          setCalls([]);
          setSource("error");
          return;
        }
        const rows = (data ?? []) as Call[];
        setCalls(sortCalls(rows.map(normalizeCall)));
        setSource("live");
        setError(null);
      });

    const channel = supabase
      .channel("calls-desk")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "calls" },
        (payload) => {
          setCalls((current) => {
            const rows = current ?? [];
            if (payload.eventType === "DELETE") {
              const id = (payload.old as { conversation_id?: string }).conversation_id;
              return rows.filter((call) => call.conversation_id !== id);
            }
            return applyRow(rows, payload.new as Call);
          });
          setSource("live");
        },
      )
      .subscribe();

    return () => {
      active = false;
      supabase.removeChannel(channel);
    };
  }, []);

  const value = useMemo(() => ({ calls, source, error }), [calls, source, error]);

  return <CallsContext.Provider value={value}>{children}</CallsContext.Provider>;
}

export function useCalls(): CallsState {
  return useContext(CallsContext);
}
