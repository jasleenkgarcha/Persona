-- Owner: Pablo. Placeholder seed rows so the dashboard has something to show. Edit freely.
insert into calls (conversation_id, caller_number, transcript, mid_call_decision, verdict, scam_score, reasons, tactics, summary, status) values
('seed_1', '+15550000001', '[{"role":"caller","text":"This is the IRS, pay in gift cards."}]', 'block', 'scam', 97, '["Impersonates IRS","Demands gift cards"]', '["authority","urgency"]', 'Classic IRS gift card scam.', 'scored'),
('seed_2', '+15550000002', '[{"role":"caller","text":"Dr. Lee''s office about Tuesday."}]', 'pass', 'legit', 8, '["Specific, plausible reason"]', '[]', 'Appointment reminder.', 'scored'),
('seed_3', '+15550000003', '[{"role":"caller","text":"Your car warranty is expiring."}]', 'block', 'scam', 90, '["Robocall script"]', '["urgency"]', 'Car warranty spam.', 'scored'),
('seed_4', '+15550000004', '[{"role":"caller","text":"Hi, it is Sam from the SHPE board."}]', 'pass', 'legit', 12, '["Known org"]', '[]', 'Org contact.', 'scored'),
('seed_5', '+15550000005', null, 'block', null, null, null, null, null, 'pending');
