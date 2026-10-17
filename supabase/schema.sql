create table calls (
  conversation_id text primary key,
  created_at timestamptz default now(),
  caller_number text,
  transcript jsonb,
  mid_call_decision text check (mid_call_decision in ('pass','block')),
  verdict text check (verdict in ('scam','legit','unsure')),
  scam_score int check (scam_score between 0 and 100),
  reasons jsonb,
  tactics jsonb,
  summary text,
  status text not null default 'pending'
    check (status in ('pending','scored','failed')),
  imessage_sent boolean not null default false
);

alter table calls enable row level security;
create policy "anon read" on calls for select to anon using (true);
alter publication supabase_realtime add table calls;
