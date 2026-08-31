"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, loadSession, Session } from "@/lib/api";
import { useRoyaleSocket } from "@/lib/ws";

type Progress = { verdict: string; tests_passed: number; tests_total: number };

export default function MatchPage({ params }: { params: { id: string } }) {
  const matchId = params.id;
  const [session, setSession] = useState<Session | null>(null);
  const [match, setMatch] = useState<any>(null);
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [mine, setMine] = useState<Progress | null>(null);
  const [theirs, setTheirs] = useState<Progress | null>(null);
  const [over, setOver] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => setSession(loadSession()), []);

  const { connected, send, on } = useRoyaleSocket(session?.access_token ?? null);

  useEffect(() => {
    if (!session) return;
    api
      .match(matchId, session.access_token)
      .then((m) => {
        setMatch(m);
        setSource(m.puzzle.starter_code ?? "");
      })
      .catch((e) => setErr(e.message));
  }, [session, matchId]);

  useEffect(() => {
    if (!connected) return;
    send({ type: "match.watch", match_id: matchId });
  }, [connected, send, matchId]);

  useEffect(() => {
    return on((msg) => {
      if (msg.scope !== "match" || msg.id !== matchId) return;
      if (msg.type === "submission.result") {
        const p: Progress = {
          verdict: msg.data.verdict,
          tests_passed: msg.data.tests_passed,
          tests_total: msg.data.tests_total,
        };
        if (msg.data.user_id === session?.user_id) setMine(p);
        else setTheirs(p);
      }
      if (msg.type === "match.over") setOver(msg.data);
    });
  }, [on, matchId, session]);

  const opponentId = useMemo(() => {
    if (!match || !session) return null;
    return match.player_a === session.user_id ? match.player_b : match.player_a;
  }, [match, session]);

  async function submit() {
    if (!session) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api.submit(matchId, source, session.access_token);
      setMine({
        verdict: r.verdict,
        tests_passed: r.tests_passed,
        tests_total: r.tests_total,
      });
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!session)
    return (
      <div className="panel">
        Please <Link href="/">pick a player</Link> first.
      </div>
    );
  if (err) return <div className="panel" style={{ color: "var(--lose)" }}>{err}</div>;
  if (!match) return <div className="panel">Loading match…</div>;

  const outcome = over
    ? over.winner_id === session.user_id
      ? "You won 🏆"
      : over.winner_id === null
        ? "Draw"
        : "You lost"
    : null;

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>{match.puzzle.title}</h2>
        <span className="pill">{match.topic.toUpperCase()}</span>
      </div>

      {over && (
        <div
          className="panel"
          style={{
            marginTop: 12,
            borderColor: outcome?.startsWith("You won") ? "var(--win)" : "var(--lose)",
          }}
        >
          <strong>{outcome}</strong> — {over.reason}.{" "}
          {session && over.ratings?.[session.user_id] && (
            <span className="muted">
              rating {over.ratings[session.user_id].old} →{" "}
              {over.ratings[session.user_id].new}
            </span>
          )}{" "}
          <Link href="/">back to lobby</Link>
        </div>
      )}

      <div className="grid2" style={{ marginTop: 16 }}>
        <div className="panel">
          <pre className="prompt">{match.puzzle.prompt_md}</pre>
          {match.puzzle.sample_testcases?.length > 0 && (
            <>
              <h4>Sample cases</h4>
              {match.puzzle.sample_testcases.map((tc: any, i: number) => (
                <pre className="prompt" key={i}>
                  in:  {JSON.stringify(tc.stdin)}
                  {"\n"}out: {JSON.stringify(tc.expected_stdout)}
                </pre>
              ))}
            </>
          )}
        </div>

        <div className="panel">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span>
              <span className={`dot ${connected ? "on" : "off"}`} />
              you: {progressText(mine)}
            </span>
            <span className="muted">opponent: {progressText(theirs)}</span>
          </div>
          <textarea
            value={source}
            onChange={(e) => setSource(e.target.value)}
            spellCheck={false}
            disabled={!!over}
          />
          <div className="row" style={{ marginTop: 10 }}>
            <button onClick={submit} disabled={busy || !!over}>
              {busy ? "Running…" : "Submit"}
            </button>
            {mine && (
              <span
                style={{
                  color: mine.verdict === "PASS" ? "var(--win)" : "var(--lose)",
                }}
              >
                {mine.verdict} ({mine.tests_passed}/{mine.tests_total})
              </span>
            )}
          </div>
          {err && <p style={{ color: "var(--lose)" }}>{err}</p>}
        </div>
      </div>
    </div>
  );
}

function progressText(p: Progress | null) {
  if (!p) return "—";
  return `${p.verdict} ${p.tests_passed}/${p.tests_total}`;
}
