"use client";

import { useEffect, useRef, useState } from "react";
import { WS_URL } from "./api";

export type Envelope = {
  scope: "user" | "match" | "leaderboard";
  id: string;
  type: string;
  data: any;
};

type Handler = (msg: Envelope) => void;

/**
 * One WebSocket for the whole session. Auto-reconnects with backoff. Consumers
 * register a handler and send() plain objects.
 */
export function useRoyaleSocket(token: string | null) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const handlers = useRef<Set<Handler>>(new Set());

  useEffect(() => {
    if (!token) return;
    let closed = false;
    let retry = 0;
    let socket: WebSocket;

    const connect = () => {
      socket = new WebSocket(`${WS_URL}/ws?token=${encodeURIComponent(token)}`);
      wsRef.current = socket;
      socket.onopen = () => {
        retry = 0;
        setConnected(true);
      };
      socket.onclose = () => {
        setConnected(false);
        if (!closed) setTimeout(connect, Math.min(1000 * 2 ** retry++, 8000));
      };
      socket.onmessage = (ev) => {
        const msg = JSON.parse(ev.data) as Envelope;
        handlers.current.forEach((h) => h(msg));
      };
    };
    connect();

    return () => {
      closed = true;
      socket?.close();
    };
  }, [token]);

  const send = (obj: unknown) => wsRef.current?.send(JSON.stringify(obj));
  const on = (h: Handler): (() => void) => {
    handlers.current.add(h);
    return () => {
      handlers.current.delete(h);
    };
  };

  return { connected, send, on };
}
