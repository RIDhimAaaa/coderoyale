"use client";

import { useEffect, useState } from "react";
import { api, loadSession, Session } from "@/lib/api";
import { useRoyaleSocket } from "@/lib/ws";

type Entry = { rank: number; username: string; rating: number; user_id: string };

export default function LeaderboardPage() {
  const [rows, setRows] = useState<Entry[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [live, setLive] = useState(false);

  useEffect(() => setSession(loadSession()), []);
  useEffect(() => {
    api.leaderboard().then(setRows).catch(() => {});
  }, []);

  const { on } = useRoyaleSocket(session?.access_token ?? null);
  useEffect(() => {
    return on((msg) => {
      if (msg.type === "leaderboard.update") {
        setRows(msg.data.top);
        setLive(true);
        setTimeout(() => setLive(false), 1200);
      }
    });
  }, [on]);

  return (
    <div className="panel">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>Leaderboard</h2>
        {live && <span className="pill" style={{ color: "var(--win)" }}>updated</span>}
      </div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Player</th>
            <th>Rating</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.user_id}>
              <td>{r.rank}</td>
              <td style={{ fontWeight: r.user_id === session?.user_id ? 700 : 400 }}>
                {r.username}
              </td>
              <td>{r.rating}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!session && (
        <p className="muted">Sign in on the lobby to see live updates.</p>
      )}
    </div>
  );
}
