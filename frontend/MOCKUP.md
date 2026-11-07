# Zasky Dashboard — Visual Mockup

**Status:** approved and implemented in the Tailwind dashboard.  
**Reference:** `docs/zasky-reference.webp`  
**Constraint:** no final React/Tailwind implementation yet. This document defines the intended layout, palette, hierarchy and class recipes.

---

## 1. Design read

The reference is a desktop productivity canvas with three layers:

1. **Large light calendar workspace** — soft off-white surface, a weekly time grid, colorful poster-like event cards, floating analytics at the bottom.
2. **Dark task rail** — near-black panel with bright pastel task cards, small filter chips and compact metadata.
3. **Thin lemon-yellow navigation rail** — a playful vertical spine with a logo, icon buttons, active dark pill and profile/settings controls.

The visual language is:

- warm light gray canvas, not pure white;
- very large rounded corners (24–30px on panels, 18–24px on cards);
- soft, deep shadows that lift the shell and cards off the canvas;
- vivid but friendly accent blocks: lemon, coral, lavender, sky, mint, rose;
- black ink typography on pastel cards and white typography on the dark rail;
- dense information, but low visual noise because each card is a single strong color;
- tiny uppercase labels, large semibold headings, generous whitespace;
- decorative translucent/fluted shapes behind the calendar, not as functional UI.

The Zasky redesign keeps that feeling but maps it to real Zasky state. No fake teams, fake progress bars or invented analytics.

---

## 2. Zasky mapping

| Reference area | Zasky equivalent |
|---|---|
| Weekly calendar | **Today’s Plan** timeline: fixed events and approved MUST/SHOULD tasks |
| Colorful event cards | Plan-item cards with disposition, time, estimate and commitment |
| Dark “Urgent Tasks” panel | **All Tasks** queue with status filters, completion, Google Calendar and Delegate actions |
| Left/center view switcher | **Plan** and **Reconcile** workspace switcher |
| Yellow icon rail | Primary navigation: Today, Tasks, Reconciliation, Calendar sync |
| Bottom floating analytics | Real planning metrics: completion, task status mix, weekly activity |
| Event card overflow menu | Task actions: complete, delegate, Google Calendar |
| Team avatars | Owner/status badge only — Zasky is single-owner |
| “Add image” toolbar | Removed; no fake media features |
| Search field | Removed; filters are enough for the current data size |

---

## 3. Layout wireframe

Desktop `xl` and above:

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│  ┌──────┐  ┌──────────────────────────────────────┐  ┌────────────────────┐  │
│  │      │  │ Today, Nov 7        [Plan] [Reconcile]│  │ Tasks     Today   │  │
│  │ rail │  │ New Goal · Commitment · Task · Sync  │  │ All Active Parked  │  │
│  │      │  ├──────────────────────────────────────┤  ├────────────────────┤  │
│  │  ▣   │  │ Mon 17  Tue 18  Wed 19  Thu 20  Fri │  │  coral task card   │  │
│  │  ◉   │  │                                      │  │  lavender task     │  │
│  │  ◌   │  │   9:00   fixed event                 │  │  sky task          │  │
│  │  ◫   │  │  10:00   MUST task card              │  │  mint task         │  │
│  │      │  │  11:00   SHOULD task card            │  │  yellow parked     │  │
│  │      │  │  12:00   decorative ribbon           │  │                    │  │
│  │      │  │  13:00                               │  │  + Add Task        │  │
│  │      │  ├──────────────────────────────────────┤  │                    │  │
│  │  ☺   │  │ [Plan health] [Task mix] [Activity]   │  │                    │  │
│  └──────┘  └──────────────────────────────────────┘  └────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

The outer shell is a single rounded application surface on a light canvas. On tablet and mobile the three columns become:

- rail → compact top bar or bottom navigation;
- main workspace → full width;
- dark task queue → collapsible section below the main workspace or a “Tasks” tab.

---

## 4. Color palette

### Core tokens

| Token | Hex | Use |
|---|---|---|
| `canvas` | `#ECECEF` | page background |
| `surface` | `#F7F7F5` | application shell |
| `paper` | `#FFFFFF` | workspace panel |
| `ink` | `#141414` | dark panel, primary text |
| `ink-soft` | `#242424` | dark panel cards |
| `muted` | `#76767D` | secondary text |
| `line` | `rgba(17,17,17,0.08)` | borders and dividers |
| `rail` | `#F2EF69` | navigation rail |
| `zest` | `#F6EA74` | lemon accent and plan highlights |
| `coral` | `#FF6B5E` | urgent/active task cards |
| `lavender` | `#C7A3F3` | focus/recovery cards |
| `sky` | `#8ED7F6` | meeting/fixed-event cards |
| `mint` | `#9DEBB5` | calm/should cards |
| `rose` | `#FF8FAE` | deep-work cards |
| `cream` | `#F4D58D` | standby accent |

### Tailwind extension

```ts
// frontend/tailwind.config.ts (proposed)
theme: {
  extend: {
    colors: {
      canvas: "#ECECEF",
      surface: "#F7F7F5",
      paper: "#FFFFFF",
      ink: "#141414",
      "ink-soft": "#242424",
      muted: "#76767D",
      line: "rgba(17,17,17,0.08)",
      rail: "#F2EF69",
      zest: "#F6EA74",
      coral: "#FF6B5E",
      lavender: "#C7A3F3",
      sky: "#8ED7F6",
      mint: "#9DEBB5",
      rose: "#FF8FAE",
      cream: "#F4D58D",
    },
    fontFamily: {
      sans: ["Manrope", "Inter", "system-ui", "sans-serif"],
      display: ["Manrope", "Inter", "system-ui", "sans-serif"],
    },
    borderRadius: {
      shell: "30px",
      panel: "26px",
      card: "22px",
      field: "14px",
    },
    boxShadow: {
      shell: "0 30px 100px -30px rgba(17,17,17,0.45)",
      card: "0 18px 34px -18px rgba(17,17,17,0.34)",
      darkcard: "0 18px 34px -18px rgba(0,0,0,0.65)",
    },
  },
}
```

### Color rules

- Ink text on every pastel card; never white on pastel.
- White text only inside the dark task panel and dark analytics card.
- Thin black/10 borders on light cards; white/10 borders on dark cards.
- Use color to identify card type/disposition, not to encode progress that does not exist in the database.
- Keep the yellow rail the only fully saturated navigation surface.

---

## 5. Type scale

| Role | Class recipe |
|---|---|
| Workspace date | `font-display text-[34px] font-semibold tracking-[-0.055em] leading-none` |
| Section heading | `font-display text-2xl font-semibold tracking-[-0.04em]` |
| Card title | `text-[17px] font-semibold tracking-[-0.02em] leading-tight` |
| Card body | `text-xs leading-relaxed text-black/60` |
| Micro label | `text-[9px] font-bold uppercase tracking-[0.18em]` |
| Meta | `text-[11px] font-medium text-muted` |
| Button | `text-xs font-semibold tracking-[-0.01em]` |
| Stat number | `font-display text-4xl font-semibold tracking-[-0.06em]` |

Font recommendation: **Manrope** (geometric, friendly, reads well at small sizes). Use `next/font/google` when implementing, with `Inter`/system fallback.

---

## 6. Component hierarchy

```text
DashboardPage
├── AmbientBackdrop
│   ├── yellow blur orb
│   ├── lavender blur orb
│   └── sky blur orb
├── AppShell
│   ├── NavigationRail
│   │   ├── BrandMark
│   │   ├── RailNav (Today, Tasks, Reconciliation)
│   │   ├── RailAction (Calendar sync)
│   │   └── RailFooter (profile/settings)
│   ├── MainWorkspace
│   │   ├── WorkspaceHeader
│   │   │   ├── DateHeading
│   │   │   ├── ViewSwitcher (Plan / Reconcile)
│   │   │   └── ActionCluster
│   │   │       ├── NewGoalButton
│   │   │       ├── NewCommitmentButton
│   │   │       ├── AddTaskButton
│   │   │       └── SyncCalendarLink
│   │   ├── PlanView
│   │   │   ├── DayStrip
│   │   │   ├── TimeGrid
│   │   │   │   ├── TimeLabels
│   │   │   │   ├── FixedEventBlock
│   │   │   │   └── PlanTaskBlock (MUST/SHOULD)
│   │   │   └── PlanStatsDock
│   │   │       ├── CompletionCard
│   │   │       ├── TaskMixCard
│   │   │       └── WeeklyActivityCard
│   │   └── ReconciliationView
│   │       ├── RecoveryHeader
│   │       └── RecoveryTimeline
│   ├── TaskQueuePanel
│   │   ├── QueueHeader (Today, avatar, add task)
│   │   ├── StatusFilterChips
│   │   ├── TaskCardList
│   │   │   └── TaskCard
│   │   │       ├── TaskMeta
│   │   │       ├── TaskTitle
│   │   │       ├── TaskTags
│   │   │       └── TaskActions (complete, calendar, delegate)
│   │   └── QueueFooter
│   └── MobileTaskDrawer
├── GoalModal
├── CommitmentModal
├── TaskModal
└── DelegateModal
```

---

## 7. Tailwind class recipes

### 7.1 Page shell

```text
min-h-screen overflow-hidden bg-canvas p-3 text-ink lg:p-5 xl:p-6
```

Ambient backdrop:

```text
pointer-events-none fixed inset-0 -z-10
before:absolute before:-left-24 before:top-24 before:h-72 before:w-72 before:rounded-full before:bg-rail/40 before:blur-[90px]
after:absolute after:-right-20 after:top-10 after:h-80 after:w-80 after:rounded-full after:bg-lavender/30 after:blur-[100px]
```

Application shell:

```text
mx-auto grid min-h-[calc(100vh-48px)] max-w-[1600px] grid-cols-[64px_minmax(0,1fr)_380px] gap-3
rounded-shell border border-black/5 bg-surface p-3 shadow-shell
xl:gap-4 xl:p-4
```

### 7.2 Navigation rail

```text
flex h-full flex-col items-center gap-4 rounded-panel bg-rail px-2 py-4
```

Brand mark:

```text
grid h-10 w-10 place-items-center rounded-2xl bg-ink text-sm font-bold text-white shadow-card
```

Nav button:

```text
grid h-11 w-11 place-items-center rounded-2xl text-ink/65 transition
hover:bg-black/10 hover:text-ink
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/30
```

Active nav button:

```text
bg-ink text-white shadow-[0_10px_20px_-10px_rgba(0,0,0,0.7)]
```

Rail separator:

```text
my-1 h-px w-6 bg-black/15
```

Profile chip at bottom:

```text
mt-auto grid h-10 w-10 place-items-center rounded-full bg-ink text-xs font-bold text-white ring-4 ring-white/60
```

### 7.3 Workspace header

```text
flex flex-wrap items-start justify-between gap-4 px-1 pb-5
```

Date heading:

```text
font-display text-[34px] font-semibold leading-none tracking-[-0.055em]
```

Date sublabel:

```text
mt-1 text-[11px] font-medium text-muted
```

Segmented switcher:

```text
inline-flex rounded-full border border-black/5 bg-black/[0.035] p-1
```

Active segment:

```text
rounded-full bg-ink px-4 py-2 text-[11px] font-semibold text-white shadow-sm
```

Inactive segment:

```text
rounded-full px-4 py-2 text-[11px] font-semibold text-muted transition hover:text-ink
```

Action cluster:

```text
flex flex-wrap items-center gap-2
```

Primary action:

```text
inline-flex h-10 items-center gap-2 rounded-full bg-ink px-4 text-xs font-semibold text-white
shadow-[0_10px_22px_-12px_rgba(0,0,0,0.8)] transition hover:-translate-y-0.5 hover:bg-ink-soft
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/30
```

Secondary action:

```text
inline-flex h-10 items-center gap-2 rounded-full border border-black/10 bg-white/80 px-4 text-xs font-semibold text-ink
shadow-sm transition hover:-translate-y-0.5 hover:bg-white
```

Calendar action:

```text
inline-flex h-10 items-center gap-2 rounded-full bg-zest px-4 text-xs font-semibold text-ink
border border-black/10 shadow-sm transition hover:-translate-y-0.5
```

### 7.4 Day strip and time grid

Day strip:

```text
grid grid-cols-[72px_repeat(5,minmax(0,1fr))] items-center gap-2 border-b border-line pb-3
```

Day label:

```text
flex items-center justify-center gap-2 text-[11px] font-medium text-muted
```

Active day number:

```text
grid h-10 w-10 place-items-center rounded-xl bg-ink text-lg font-semibold text-white shadow-card
```

Inactive day number:

```text
text-lg font-semibold text-ink/35
```

Time grid:

```text
relative grid h-[600px] grid-cols-[72px_repeat(5,minmax(0,1fr))] gap-2 overflow-hidden rounded-panel
```

Time label:

```text
pr-2 text-right text-[10px] font-medium text-muted/70
```

Grid line:

```text
col-span-full border-t border-black/[0.055]
```

Background day column:

```text
rounded-[18px] bg-white/45 ring-1 ring-inset ring-black/[0.035]
```

Decorative ribbon:

```text
pointer-events-none absolute bottom-10 left-[38%] top-16 w-28 -rotate-2 rounded-[40px]
bg-[conic-gradient(from_180deg,rgba(199,163,243,0.9),rgba(142,215,246,0.7),rgba(246,234,116,0.65),rgba(199,163,243,0.9))]
opacity-30 blur-[2px]
```

### 7.5 Plan task cards

Base:

```text
group absolute rounded-[22px] border border-black/10 p-3.5 text-ink shadow-card
transition duration-200 hover:-translate-y-1 hover:shadow-[0_24px_42px_-20px_rgba(17,17,17,0.42)]
```

MUST variant:

```text
bg-zest
```

SHOULD variant:

```text
bg-mint
```

Fixed event variant:

```text
bg-sky/90
```

Deep-work variant:

```text
bg-rose
```

Focus/recovery variant:

```text
bg-lavender
```

Completed variant:

```text
bg-white/60 text-ink/45 grayscale-[0.25]
```

Card micro label:

```text
text-[9px] font-bold uppercase tracking-[0.18em] text-black/50
```

Card title:

```text
mt-1 text-[16px] font-semibold leading-tight tracking-[-0.02em]
```

Card meta row:

```text
mt-2 flex flex-wrap items-center gap-1.5 text-[10px] font-medium text-black/55
```

Card top-right action:

```text
grid h-7 w-7 place-items-center rounded-full bg-white/45 text-ink/70 opacity-0 transition
group-hover:opacity-100 hover:bg-white/80
```

Disposition pill:

```text
rounded-full bg-black/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.12em]
```

### 7.6 Dark task queue panel

```text
flex h-full min-h-0 flex-col rounded-panel bg-ink p-4 text-white shadow-darkcard
```

Queue header:

```text
flex items-center justify-between gap-3 pb-3
```

Queue title:

```text
font-display text-2xl font-semibold tracking-[-0.045em]
```

Queue date:

```text
text-[10px] font-medium uppercase tracking-[0.14em] text-white/45
```

Filter chip:

```text
rounded-full border border-white/10 bg-white/[0.06] px-3 py-1.5 text-[10px] font-semibold text-white/60
transition hover:bg-white/10 hover:text-white
```

Active filter chip:

```text
bg-white text-ink border-white
```

Task list:

```text
mt-3 flex-1 space-y-3 overflow-y-auto pr-1
scrollbar-thin scrollbar-thumb-white/15
```

Task card base:

```text
group relative rounded-[22px] p-4 text-ink shadow-darkcard transition duration-200
hover:-translate-y-0.5 hover:shadow-[0_22px_40px_-20px_rgba(0,0,0,0.75)]
```

Task card variants (cycle by task/tone):

```text
bg-coral
bg-lavender
bg-sky
bg-mint
bg-zest
```

Completed task card:

```text
bg-white/10 text-white/55 ring-1 ring-inset ring-white/10
```

Task card top row:

```text
flex items-center justify-between gap-2 text-[9px] font-bold uppercase tracking-[0.14em] text-black/55
```

Task card title:

```text
mt-2 text-[18px] font-semibold leading-tight tracking-[-0.025em]
```

Task card meta:

```text
mt-2 flex flex-wrap items-center gap-1.5 text-[10px] font-medium text-black/55
```

Task action row:

```text
mt-3 flex flex-wrap items-center gap-1.5
```

Complete checkbox:

```text
grid h-7 w-7 place-items-center rounded-lg border border-black/20 bg-white/35 text-ink
transition hover:bg-white/60
```

Calendar icon link:

```text
grid h-7 w-7 place-items-center rounded-full border border-black/10 bg-white/45 text-[12px]
text-ink/70 transition hover:bg-white/80
```

Delegate button:

```text
inline-flex items-center gap-1 rounded-full bg-ink px-3 py-1.5 text-[9px] font-bold
uppercase tracking-[0.08em] text-white transition hover:bg-ink-soft
```

Add task footer:

```text
mt-3 flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2.5
```

### 7.7 Floating analytics dock

Container on desktop:

```text
pointer-events-none absolute inset-x-4 bottom-3 z-10 grid grid-cols-[1.1fr_0.95fr_1fr] gap-3
```

On smaller screens:

```text
static mt-4 grid grid-cols-1 gap-3 md:grid-cols-3
```

Dark completion card:

```text
pointer-events-auto rounded-[24px] bg-ink p-5 text-white shadow-darkcard
```

Light metric card:

```text
pointer-events-auto rounded-[24px] border border-black/[0.06] bg-white/85 p-5 shadow-card backdrop-blur-xl
```

Ring chart wrapper:

```text
relative grid h-28 w-28 place-items-center rounded-full
```

Metric number:

```text
font-display text-3xl font-semibold tracking-[-0.06em]
```

Metric label:

```text
text-[9px] font-bold uppercase tracking-[0.16em] text-muted
```

Bar chart area:

```text
mt-4 flex h-24 items-end gap-2
```

Bar:

```text
w-full rounded-t-full bg-lavender/70 transition-all duration-500
```

Highlighted bar:

```text
bg-coral
```

### 7.8 Reconciliation timeline

```text
space-y-4
```

Recovery card:

```text
rounded-panel border border-black/[0.06] bg-white/75 p-5 shadow-card backdrop-blur-xl
```

Timeline marker:

```text
absolute -left-[19px] top-6 h-3 w-3 rounded-full border-[3px] border-surface bg-coral
```

Recovery meta:

```text
flex flex-wrap items-center justify-between gap-3
```

Disposition badge MUST:

```text
rounded-full bg-zest px-2.5 py-1 text-[9px] font-bold uppercase tracking-[0.12em] text-ink
```

Disposition badge SHOULD:

```text
rounded-full bg-mint px-2.5 py-1 text-[9px] font-bold uppercase tracking-[0.12em] text-ink
```

### 7.9 Modals

Backdrop:

```text
fixed inset-0 z-50 grid place-items-center bg-black/35 p-4 backdrop-blur-md
```

Card:

```text
w-full max-w-xl rounded-shell border border-white/70 bg-surface p-6 shadow-shell
```

Wide card:

```text
max-w-3xl
```

Header:

```text
flex items-start justify-between gap-4 pb-5
```

Title:

```text
font-display text-2xl font-semibold tracking-[-0.04em]
```

Close button:

```text
grid h-9 w-9 place-items-center rounded-full border border-black/10 bg-white/70 text-ink/60
transition hover:bg-white hover:text-ink
```

Form grid:

```text
grid gap-4 md:grid-cols-2
```

Full-width field:

```text
md:col-span-2
```

Field label:

```text
text-[9px] font-bold uppercase tracking-[0.16em] text-muted
```

Input:

```text
mt-1.5 h-11 w-full rounded-field border border-black/10 bg-white px-3.5 text-sm text-ink
outline-none transition placeholder:text-muted/55
focus:border-ink/30 focus:ring-2 focus:ring-ink/10
```

Textarea:

```text
mt-1.5 min-h-24 w-full rounded-field border border-black/10 bg-white px-3.5 py-3 text-sm text-ink
outline-none transition placeholder:text-muted/55
focus:border-ink/30 focus:ring-2 focus:ring-ink/10
```

Form footer:

```text
flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end
```

Primary submit:

```text
inline-flex h-11 items-center justify-center rounded-full bg-ink px-5 text-xs font-semibold text-white
transition hover:bg-ink-soft disabled:cursor-wait disabled:opacity-50
```

Cancel:

```text
inline-flex h-11 items-center justify-center rounded-full border border-black/10 bg-white px-5 text-xs font-semibold text-ink
transition hover:bg-white/70
```

Delegate output:

```text
max-h-[52vh] overflow-auto rounded-[18px] border border-black/10 bg-white/75 p-5
whitespace-pre-wrap font-sans text-[13px] leading-relaxed text-ink/80
```

Delegate loading block:

```text
flex items-center gap-4 rounded-[18px] border border-lavender/30 bg-lavender/15 p-5
```

### 7.10 Empty and loading states

Empty card:

```text
grid min-h-64 place-items-center rounded-panel border border-dashed border-black/10 bg-white/45 p-8 text-center
```

Empty icon:

```text
grid h-14 w-14 place-items-center rounded-2xl bg-zest text-2xl shadow-card
```

Skeleton:

```text
animate-pulse rounded-panel bg-black/[0.045]
```

---

## 8. View behavior

### Plan view

- Header date is today’s local date.
- Day strip shows the current week with today’s number in the black tile.
- Time grid shows 09:00–17:00 by default with active plan items and fixed events.
- MUST items use `bg-zest`; SHOULD items use `bg-mint`; fixed events use `bg-sky`.
- Completed items are desaturated and moved to the bottom of the card list inside their block.
- Bottom dock shows:
  - completion ring: completed / total tasks;
  - task mix: active, parked, completed;
  - weekly bars: tasks by scheduled date.
- Decorative fluted ribbon sits behind the timeline at low opacity.

### Reconciliation view

- Same shell and dark task queue, but the main area shows recovery history.
- Each recovery card uses white glass, a coral timeline dot and small fresh/kept/moved chips.
- The date is the recovery date; the plan items keep their existing MUST/SHOULD color coding.

### Task queue panel

- Always visible on desktop.
- Filters: `All`, `Active`, `Parked`, `Completed`.
- Cards cycle through coral, lavender, sky, mint and zest.
- Each incomplete card includes:
  - completion checkbox;
  - Google Calendar 📅 link;
  - Delegate to AI pill.
- Completed cards become translucent dark cards with a check and no delegate button.
- `+ Add Task` appears in the queue header and footer.

### Mobile

- Rail becomes a fixed bottom navigation bar with four icons and safe-area padding.
- Main workspace becomes single column.
- Task queue becomes a full-width section below the plan, or a full-screen drawer opened from the bottom nav.
- Time grid switches to an agenda list (no horizontal week columns).
- Analytics dock becomes a horizontal scroll row or a 1-column stack.
- Modals use full-height sheets with `rounded-t-shell`.

---

## 9. Motion and interaction

- Shell fades/rises once on load: `animate-[rise_500ms_ease-out_both]`.
- Cards hover with `-translate-y-1` and a slightly deeper shadow.
- Rail active pill transitions with `duration-200`.
- Modals scale from `0.97` to `1` with opacity.
- Delegate modal shows a pulsing lavender loading block while waiting.
- Bar/ring charts animate from zero on first mount.
- Respect `prefers-reduced-motion`: disable transforms and chart animation.

---

## 10. Accessibility

- All pastel cards use `text-ink`; minimum contrast is black on light pastel.
- Icon-only buttons need `aria-label` and `title`.
- Focus rings: `focus-visible:ring-2 focus-visible:ring-ink/30 focus-visible:ring-offset-2`.
- Status is never color-only: every card carries a small text pill.
- Modal traps focus and closes with Escape.
- The calendar grid is decorative; the actual ordered plan is also available as a semantic list for screen readers.
- Touch targets are at least 40px on mobile.

---

## 11. Implementation notes for after approval

1. Add Tailwind CSS, PostCSS and a small `cn()` utility (`clsx` + `tailwind-merge`).
2. Move color/shadow/radius tokens into `tailwind.config.ts`.
3. Split the current single `page.tsx` into components under `frontend/components/`:
   - `shell/`, `calendar/`, `tasks/`, `stats/`, `modals/`.
4. Keep the existing API endpoints and data model unchanged.
5. Replace global CSS with Tailwind layers plus a small amount of custom CSS for the fluted ribbon and chart masks.
6. Preserve all current behavior: create goal/commitment/task, complete task, delegate, Google Calendar links, calendar feed, modals and reconciliation history.
7. Verify at 1440px, 1280px, 1024px, 768px and 390px.
8. Run `npm run build` and the backend tests after implementation.

---

## 12. Approval checklist

Please confirm:

- [ ] Three-column shell: yellow rail, light main workspace, dark task queue.
- [ ] Main workspace uses a calendar-like Today timeline rather than a plain list.
- [ ] All Tasks lives permanently in the dark right panel (and becomes a mobile section/tab).
- [ ] Bottom floating analytics use only real Zasky data (completion, status mix, weekly activity).
- [ ] Pastel card palette and black typography match the reference.
- [ ] New Goal / New Commitment / Add Task / Sync to Calendar / Delegate actions remain available.
- [ ] No fake teams, fake progress bars or invented features.

Once approved, I’ll implement the Tailwind version and keep the existing API behavior intact.
