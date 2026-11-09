"use client";

import { ArrowUp } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const SCROLL_THRESHOLD = 260;

export function ScrollToTopButton() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const update = () => {
      const queues = document.querySelectorAll<HTMLElement>(
        "[data-task-queue-scroll]",
      );
      const queueScrolled = Array.from(queues).some(
        (queue) => queue.scrollTop > SCROLL_THRESHOLD,
      );
      setVisible(window.scrollY > SCROLL_THRESHOLD || queueScrolled);
    };

    // Capture phase catches scroll events from the task queue as well as the
    // document/window, without coupling the button to the queue component.
    document.addEventListener("scroll", update, true);
    window.addEventListener("scroll", update, { passive: true });
    update();
    return () => {
      document.removeEventListener("scroll", update, true);
      window.removeEventListener("scroll", update);
    };
  }, []);

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
      tabIndex={visible ? 0 : -1}
      className={cn(
        "fixed bottom-24 right-4 z-40 grid h-12 w-12 place-items-center rounded-full border border-white/15 bg-ink text-white shadow-[0_16px_34px_-12px_rgba(0,0,0,0.75)] transition duration-200 hover:-translate-y-0.5 hover:bg-ink-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/40 lg:bottom-8 lg:right-8",
        visible
          ? "translate-y-0 opacity-100"
          : "pointer-events-none translate-y-3 opacity-0",
      )}
    >
      <ArrowUp size={18} strokeWidth={2.4} />
    </button>
  );
}
