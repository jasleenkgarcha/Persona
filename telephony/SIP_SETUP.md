# Photon <-> ElevenLabs SIP setup (Owner: Ian)

Source: https://photon.codes/docs/beta/cookbooks/voice/elevenlabs.md (beta platform)
Values below are copied from that cookbook. Anything marked UNVERIFIED we have
not seen work on our own account yet.

## Prerequisites (check before touching anything)
- Photon project with an eligible **SMS number**, WhatsApp number, or
  **dedicated** iMessage line.
  **A shared iMessage assignment does NOT support Voice.** The free shared
  line is for texting the verdict only, never for the call leg.
- Permission to manage the project's Voice profiles.
- An ElevenLabs agent that is **published** (needed before number import).
- A second phone to call from.

## Order of operations
1. Photon: create Voice profile (SIP)
2. Photon: enable outbound + save password (ONE-TIME DISPLAY)
3. ElevenLabs: import number from SIP trunk
4. ElevenLabs: assign agent to the number
5. Photon: set inbound destination
6. Test inbound, then outbound

## Step 1 - Photon Voice profile
Project -> **Voice** -> under **Lines** find your number.
If no default profile exists, **Set up default**. Then **SIP** -> **Create profile**.
Editing a profile affects every number using it.

## Step 2 - Photon outbound credentials
**Outbound calls** -> **Digest algorithm** = `SHA-256 (recommended)`
-> **Enable outbound** -> copy password -> **I saved it**.

The password is shown **once**. If lost, use **Rotate** and update every
service using it. These SIP credentials are NOT the Photon API key.

Record (store outside git):
- SIP server + port: `sip.photon.codes:5061` (confirm against your own profile)
- Username: ________
- Password: ________  (never commit)

## Step 3 - ElevenLabs number import
**Deploy -> Phone Numbers -> Import number -> From SIP Trunk**
- Label: e.g. `Photon demo`
- Phone number: international format, `+` and country code

### Inbound Configuration (Photon -> ElevenLabs)
| Field | Value |
|---|---|
| Media Encryption | Allowed |
| Allowed Numbers | empty (= All numbers) |
| Allowed Source IP Addresses | `0.0.0.0/0` (= All addresses) |
| Remote Domains | empty initially |
| SIP Trunk Username / Password | empty (no inbound auth) |

### Outbound Configuration (ElevenLabs -> Photon)
| Field | Value |
|---|---|
| Address | `sip.photon.codes:5061` (no `sip:` / `sips:` prefix) |
| Transport Type | TLS |
| Media Encryption | Allowed |
| Enabled Codecs | G.722, PCMU, PCMA |
| Custom Headers | empty |
| SIP Trunk Username | Photon outbound username |
| SIP Trunk Password | saved outbound password |

Supply both credential fields on first import even though ElevenLabs marks
them optional. After import the number shows **Provider: SIP Trunk**.

## Step 4 - Assign agent
On the number's page, **Agent** dropdown (starts at **No agent**) -> your agent.
If **Branch** appears, leave **Follow traffic split**.

## Step 5 - Photon inbound destination
Profile -> **Inbound calls** -> **Enable inbound** if needed.
- SIP address / Destination: `sips:sip.rtc.elevenlabs.io:5061`
- Transport: TLS
- SIP credentials: leave empty (matches ElevenLabs inbound config)

When editing an existing destination, move focus out of the field to save.

Media encryption: keep Photon on **Auto**, both ElevenLabs media settings on
**Allowed**. To require encryption, enable **Require encrypted calls** in
Photon and set ElevenLabs to **Required** - both directions must support it.

## Step 6 - Test
- **Inbound:** call the Photon number from the second phone. Agent should
  answer, audio both ways, call ends cleanly in ElevenLabs.
- **Outbound:** ElevenLabs number page -> **Outbound call** -> agent + branch
  -> recipient with `+` and country code -> **Send Test Call**.
  A saved trunk or an accepted request does NOT prove delivery. Confirm the
  recipient's phone actually rings.

## Troubleshooting (from the cookbook)
- Enable **SIP Messages** on the imported number page before debugging.
  Record attempt time, conversation ID, and SIP response before changing settings.
- Auth failures: recheck outbound username/password and that SHA-256 is selected.
- Missing or one-way audio: check negotiated codec and both media-encryption settings.
- "Initiated" but no ring: check **Conversations** for the attempt, verify the
  saved hostname against Photon's connection details.
- **Transfer / hangup failing validation:** add the domain covered by your
  Photon SIP server's certificate under **Remote Domains**. This is the first
  thing to try if `transfer_to_number` fails.

## Still UNVERIFIED (our known unknowns)
- `transfer_to_number` in Conference mode over this trunk. The cookbook does
  not document it; it only covers the **Outbound call** dialog. The Remote
  Domains note above implies transfer exists and may need cert config.
- Whether `system__caller_id` appears in the post-call webhook payload.
  `backend/normalize.py::extract_caller_number` is a guess until we capture
  a real payload.
- Photon SMS number provisioning time. Not documented; US SMS may need
  A2P 10DLC brand/campaign registration with carrier review.
- Whether the free shared iMessage line requires the recipient to text it
  first before it can message them.
