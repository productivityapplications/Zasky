# Zasky — Demo Video Plan

**Maximum:** 180 seconds  
**Target:** 120–150 seconds  
**Status:** Produced 2026-11-06. The headless-host limitation was handled as a **local protocol/transcript demo**, explicitly labeled; no fabricated Discord UI. Final file: `artifacts/demo/zasky-demo.mp4` (97 seconds).

## Story

Show the defining value: a real Switch-connected agent in the same private chat room as its owner, holding the plan and rebuilding it after a disruption. Avoid a generic feature tour.

## Required environment

- Isolated Switch workspace and Discord test server/private channel.
- Deterministic synthetic demo data only.
- One configured demo owner; no real personal task names, private IDs, hostnames or URLs.
- Verified, tagged commit and stable service deployment.
- Clean Discord client session and notifications disabled.
- Demo seed/reset script documented; do not use production DB.
- Playwright capture if Discord web automation is reliable and permitted. Otherwise use equivalent desktop capture of the real running client. The capture must show actual application behavior, not a fabricated UI.

## Timed sequence and narration draft

| Time | Screen action | Narration |
|---|---|---|
| 0:00–0:12 | Show private Discord room and Zasky responding through Switch | "This is Zasky. It lives in my chat, where the plan and the decisions about that plan stay together." |
| 0:12–0:30 | Show one sample year goal and a month commitment with evidence | "The plan has a spine: year goals become commitments I choose for the month. Zasky checks the numbers; it does not invent work for me." |
| 0:30–0:50 | Show week placement proposal, 65% capacity and visible slack; approve | "I choose the actual work. Zasky places it into the week while protecting capacity for real life." |
| 0:50–1:10 | Show day plan from approved week pool, one must, up to two should, battery check and backplan | "Today's tasks come only from that approved pool. The plan is small, and it tells me the latest workable wake time." |
| 1:10–1:43 | Type a disruption: "Back. A two-hour call ran over; it's 4pm." Show reconcile, revised schedule and week arithmetic | "Then the day breaks. Instead of starting over, I tell Zasky what happened. It rebuilds the rest of the day and shows whether the week still holds." |
| 1:43–2:00 | Approve proposal and show resulting plan | "Nothing changes until I approve. The plan adjusts, but the commitments remain mine." |
| 2:00–2:12 | Close on message | "Zasky doesn't give me discipline. It makes coming back cheap." |

Target duration: approximately 132 seconds. Re-time after actual recording; never speed narration to force the duration.

## Capture procedure

1. Reset isolated demo DB and seed the approved synthetic year/month/week data.
2. Verify fixed events, time zone and current demo clock are deterministic.
3. Start Zasky and Switch; confirm WebSocket is connected and Discord bridge healthy.
4. Run the exact sequence once as rehearsal; reset state.
5. Capture clean browser/client session using Playwright or screen recorder.
6. Capture audio separately or use verified voiceover workflow.
7. Review footage for actual visible response alignment; remove waiting gaps and accidental private notifications.
8. Add captions when feasible and verify they match narration.
9. Redact room IDs, participant IDs, hostnames, private links, tokens, environment values and real personal data.
10. Render MP4 and inspect start, middle and end; verify playback, clear audio and duration <=180 seconds.
11. Save final video, narration script, demo seed description and production notes in the intake-approved output path.

## Voice/TTS

- Check current Google AI voice/TTS product, free quota, terms, geography/availability and required credentials at production time.
- Do not assume a free tier is unlimited or that a model is included in a free plan.
- Do not incur charges without the operator's explicit spend authority.
- If Google AI TTS is unavailable or paid, use a genuinely free, permitted local TTS or operator-recorded narration. Record the substitution.
- Do not use an unlicensed voice clone or upload private user recordings.

## Produced deliverables

- `artifacts/demo/zasky-demo.mp4` — 97 seconds, 1280×720, H.264/AAC
- `artifacts/demo/narration-script.md`
- `artifacts/demo/production-notes.md`
- `artifacts/demo/demo-seed.md`
- `artifacts/demo/transcript.txt`
- `scripts/seed_demo.py`, `scripts/demo_transcript.py`,
  `scripts/build_demo_video.py`

The demo uses the real OpenRouter model and the real seven-tool/domain path, but
renders a transcript rather than a Discord window. This is stated on every slide
and in the narration.

## Final verification checklist

- [ ] Runtime <=180 seconds.
- [ ] All scenes show real, verified product behavior.
- [ ] Every narrated claim is visible on screen.
- [ ] No long silence, clipped speech or rushed narration.
- [ ] Captions reviewed where used.
- [ ] No personal data, tokens, private URLs or private repository details.
- [ ] Audio and video playback verified.
- [ ] Exact deployed commit/version recorded in `AI_HANDOFF.md`.
