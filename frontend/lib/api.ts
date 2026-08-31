"use client";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

export type Session = {
  access_token: string;
  user_id: string;
  username: string;
  rating: number;
};

const KEY = "coderoyale.session";

export function loadSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function saveSession(s: Session | null) {
  try {
    if (s) window.localStorage.setItem(KEY, JSON.stringify(s));
    else window.localStorage.removeItem(KEY);
  } catch {
    /* private mode / storage disabled */
  }
}

async function req<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  login: (username: string, password: string) =>
    req<Session>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  leaderboard: () =>
    req<{ rank: number; username: string; rating: number; user_id: string }[]>(
      "/leaderboard",
    ),
  match: (id: string, token: string) => req<any>(`/matches/${id}`, {}, token),
  submit: (id: string, source: string, token: string) =>
    req<any>(
      `/matches/${id}/submit`,
      { method: "POST", body: JSON.stringify({ source }) },
      token,
    ),
};
