import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { ExecutionSections } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value: string, long = false): string {
  const parts = value.split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) {
    return value;
  }
  const date = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2], 12));
  return new Intl.DateTimeFormat("en-US", {
    weekday: long ? "long" : "short",
    month: long ? "long" : "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function formatLongDate(value: string): string {
  return formatDate(value, true);
}

export function localDateString(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

export function parseTimeLabel(label: string | null): number | null {
  if (!label) {
    return null;
  }
  const match = label.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
  if (!match) {
    return null;
  }
  let hour = Number(match[1]) % 12;
  if (match[3].toUpperCase() === "PM") {
    hour += 12;
  }
  return hour * 60 + Number(match[2]);
}

export function splitExecutionOutput(output: string): ExecutionSections {
  const section = (number: number, next?: number) => {
    const start = output.search(new RegExp(`^##\\s*${number}\\.\\s*`, "im"));
    if (start < 0) {
      return "";
    }
    const contentStart = output.indexOf("\n", start);
    const remainder = contentStart >= 0 ? output.slice(contentStart + 1) : "";
    if (next === undefined) {
      return remainder.trim();
    }
    const end = remainder.search(new RegExp(`^##\\s*${next}\\.\\s*`, "im"));
    return (end >= 0 ? remainder.slice(0, end) : remainder).trim();
  };
  return {
    deliverable: section(1, 2) || output.trim(),
    whatIDid: section(2, 3),
    checklist: section(3),
  };
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload && typeof payload.detail === "string"
        ? payload.detail
        : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return payload as T;
}

export async function fetchJson<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, { cache: "no-store", signal });
  return parseResponse<T>(response);
}

export async function sendJson<T>(
  path: string,
  body: unknown,
  method = "POST",
): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseResponse<T>(response);
}
