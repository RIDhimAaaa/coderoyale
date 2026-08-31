"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, loadSession, saveSession, Session } from "@/lib/api";
import { useRoyaleSocket } from "@/lib/ws";

const DEMO_USERS = ["alice", "bob", "carol", "dave", "erin"];
const TOPICS = ["dsa", "backend"] as const;

export default function Lobby() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [queued, setQueued] = useState<string | null>(null);

  useEffect(() => setSession(loadSession()), []);

  const { connected, send, on } = useRoyaleSocket(session?.access_token ?? null);

  useEffect(() => {
    return on((msg) => {
      if (msg.type === "match.found") {
        router.push(`/match/${msg.data.match_id}`);
      }
    });
  }, [on, router]);

  async function pick(username: string) {
    setError(null);
    try {
      const s = await api.login(username, "password");
      saveSession(s);
      setSession(s);
    } catch (e: any) {
      setError(e.message);
    }
  }

  function logout() {
    saveSession(null);
    setSession(null);
    setQueued(null);
  }

  function joinQueue(topic: string) {
    send({ type: "queue.join", topic });
    setQueued(topic);
  }
  function leaveQueue() {
    send({ type: "queue.leave" });
    setQueued(null);
  }

  if (!session) {
    return (
      <div className="panel">
        <h2>Pick a demo player</h2>
        <p className="muted">
          Seeded accounts, password <code>password</code>. Open two browser tabs as
          two different players to start a match.
        </p>
        <div className="row">
          {DEMO_USERS.map((u) => (
            <button key={u} className="secondary" onClick={() => pick(u)}>
              {u}
            </button>
          ))}
        </div>
        {error && <p style={{ color: "var(--lose)" }}>{error}</p>}
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          Signed in as <strong>{session.username}</strong>{" "}
          <span className="pill">{session.rating}</span>{" "}
          <span className="muted">
            <span className={`dot ${connected ? "on" : "off"}`} />
            {connected ? "connected" : "connecting…"}
          </span>
        </div>
        <button className="secondary" onClick={logout}>
          switch player
        </button>
      </div>

      <h3 style={{ marginTop: 24 }}>Find a match</h3>
      {queued ? (
        <div className="row">
          <span>Searching for an opponent in <strong>{queued}</strong>…</span>
          <button className="secondary" onClick={leaveQueue}>
            cancel
          </button>
        </div>
      ) : (
        <div className="row">
          {TOPICS.map((t) => (
            <button key={t} disabled={!connected} onClick={() => joinQueue(t)}>
              Queue: {t.toUpperCase()}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
