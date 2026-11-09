"use client";

import { ArrowUp } from "lucide-react";

export function ScrollToTopButton() {
  const scrollToTop = () => {
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const behavior: ScrollBehavior = reducedMotion ? "auto" : "smooth";

    window.scrollTo({ top: 0, behavior });
    document
      .querySelectorAll<HTMLElement>("[data-task-queue-scroll]")
      .forEach((queue) => queue.scrollTo({ top: 0, behavior }));
  };

  return (
    <button
      type="button"
      onClick={scrollToTop}
      aria-label="Scroll to top"
      title="Scroll to top"
      className="grid h-11 w-11 place-items-center rounded-2xl text-ink/65 transition hover:bg-black/10 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/30"
    >
      <ArrowUp size={18} strokeWidth={2} />
    </button>
  );
}
