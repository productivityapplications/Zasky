"use client";

import { RotateCcw } from "lucide-react";

import { cn, formatDate } from "@/lib/utils";
import type { Reconciliation } from "@/lib/types";
import { EmptyState } from "@/components/ui";

export function ReconciliationView({
  reconciliations,
}: {
  reconciliations: Reconciliation[];
}) {
  return (
    <section className="pb-5" aria-label="Reconciliation history">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-muted">
            Recovery trail
          </p>
          <h2 className="mt-1 font-display text-3xl font-semibold tracking-[-0.05em]">
            Reconciliation History
          </h2>
        </div>
        <span className="rounded-full border border-black/10 bg-white/70 px-3 py-1.5 text-[10px] font-medium text-muted">
          {reconciliations.length} approved plans
        </span>
      </div>

      {reconciliations.length ? (
        <div className="relative space-y-3 pl-5">
          <div className="absolute bottom-4 left-[5px] top-4 w-px bg-black/10" />
          {reconciliations.map((entry) => (
            <article
              key={entry.id}
              className="relative rounded-panel border border-black/[0.06] bg-white/75 p-5 shadow-card backdrop-blur-xl"
            >
              <span className="absolute -left-[19px] top-6 h-3 w-3 rounded-full border-[3px] border-surface bg-coral" />
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-coral">
                    {formatDate(entry.date, true)}
                  </p>
                  <h3 className="mt-1 font-display text-xl font-semibold tracking-[-0.03em]">
                    Recovery plan · revision {entry.revision}
                  </h3>
                </div>
                <span className="rounded-full bg-lavender/25 px-2.5 py-1 text-[9px] font-bold uppercase tracking-[0.12em] text-ink/70">
                  {entry.battery} battery
                </span>
              </div>
              <p className="mt-3 max-w-2xl text-xs leading-relaxed text-muted">
                {entry.summary ??
                  "Recovery approved. Kept work today and moved or dropped what no longer fit."}
              </p>
              {entry.latest_wake_display ? (
                <p className="mt-1 text-[10px] text-muted/70">
                  Latest wake {entry.latest_wake_display}
                </p>
              ) : null}

              <div className="mt-4 space-y-1.5 border-t border-black/[0.06] pt-4">
                {entry.items.map((item) => (
                  <div key={item.id} className="flex items-center gap-2">
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[8px] font-bold uppercase tracking-[0.12em]",
                        item.disposition === "must"
                          ? "bg-zest text-ink"
                          : "bg-mint text-ink",
                      )}
                    >
                      {item.disposition}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-ink/75">
                      {item.title}
                    </span>
                    <span className="shrink-0 text-[9px] text-muted/65">
                      {item.planned_start_display ?? "—"} –{" "}
                      {item.planned_end_display ?? "—"}
                    </span>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No reconciliations yet."
          body="When a disrupted day is recovered, Zasky records the approved recovery plan here."
          icon={<RotateCcw size={20} />}
        />
      )}
    </section>
  );
}
