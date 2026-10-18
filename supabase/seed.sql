-- Seed data for the dashboard: 5 fake calls (2 scam, 2 legit, 1 pending).
-- Run in the Supabase SQL Editor after the schema. Safe to re-run.
-- All ids start with 'seed_' so they are easy to find or remove:
--   delete from public.calls where conversation_id like 'seed_%';

insert into public.calls
  (conversation_id, created_at, caller_number, transcript, mid_call_decision,
   verdict, scam_score, reasons, tactics, summary, status, imessage_sent)
values
(
  'seed_scam_irs',
  now() - interval '3 hours',
  '+18005550142',
  '[
    {"role":"agent","text":"Hi, I''m an AI assistant screening calls. Who''s calling and why?"},
    {"role":"caller","text":"This is Officer Daniels from the IRS. There is a warrant out for your arrest over unpaid taxes."},
    {"role":"agent","text":"Can you tell me which department you''re with?"},
    {"role":"caller","text":"Do not hang up. You must pay today with gift cards or you will be arrested."}
  ]'::jsonb,
  'block', 'scam', 96,
  '["Claims to be the IRS and threatens arrest", "Demands payment by gift card", "Refuses to answer a direct question about the department"]'::jsonb,
  '["impersonation", "urgency", "threats", "untraceable payment"]'::jsonb,
  'Caller posed as an IRS officer, threatened arrest, and demanded gift card payment. Blocked.',
  'scored', true
),
(
  'seed_legit_dentist',
  now() - interval '2 hours 30 minutes',
  '+18135550177',
  '[
    {"role":"agent","text":"Hi, I''m an AI assistant screening calls. Who''s calling and why?"},
    {"role":"caller","text":"This is Maria from Bayshore Dental calling to confirm your cleaning on Tuesday at 3 PM."},
    {"role":"agent","text":"Thanks. Is there anything you need from the owner?"},
    {"role":"caller","text":"Just a yes or no on the time. They can call us back at the office line."}
  ]'::jsonb,
  'pass', 'legit', 6,
  '["Specific, plausible appointment reminder", "No request for money or personal information", "Offers a callback to the office line"]'::jsonb,
  '[]'::jsonb,
  'Routine appointment confirmation from a dental office. Passed through.',
  'scored', true
),
(
  'seed_scam_tech_support',
  now() - interval '90 minutes',
  '+12125550163',
  '[
    {"role":"agent","text":"Hi, I''m an AI assistant screening calls. Who''s calling and why?"},
    {"role":"caller","text":"I''m calling from Microsoft Support. Your computer has a virus and we need remote access right now."},
    {"role":"agent","text":"Which computer are you referring to?"},
    {"role":"caller","text":"Just go to your computer and install the program I send. It is urgent."}
  ]'::jsonb,
  'block', 'scam', 93,
  '["Unsolicited call claiming a virus", "Asks for remote access", "Cannot say which device is affected"]'::jsonb,
  '["impersonation", "urgency", "remote access request"]'::jsonb,
  'Classic tech-support scam asking for remote access. Blocked.',
  'scored', true
),
(
  'seed_legit_pharmacy',
  now() - interval '45 minutes',
  '+18135550119',
  '[
    {"role":"agent","text":"Hi, I''m an AI assistant screening calls. Who''s calling and why?"},
    {"role":"caller","text":"This is the pharmacy at Harbor Drugs. Your prescription is ready for pickup."},
    {"role":"agent","text":"Do you need anything else from the owner?"},
    {"role":"caller","text":"No, it is ready any time before 8 tonight. No need to call back."}
  ]'::jsonb,
  'pass', 'legit', 11,
  '["Pharmacy pickup notice with no request for payment or details", "Calm tone and no pressure"]'::jsonb,
  '[]'::jsonb,
  'Prescription pickup notice from a pharmacy. Passed through.',
  'scored', true
),
(
  'seed_pending_unknown',
  now() - interval '2 minutes',
  '+17275550188',
  null,
  'block',
  null, null, null, null, null,
  'pending', false
)
on conflict (conversation_id) do nothing;
