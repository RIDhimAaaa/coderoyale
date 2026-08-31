import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Code Royale",
  description: "Real-time 1v1 competitive coding",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="wrap">
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 20 }}>
            <Link href="/" style={{ fontWeight: 700, fontSize: 18, textDecoration: "none" }}>
              ⚔️ Code Royale
            </Link>
            <Link href="/leaderboard" className="muted">
              Leaderboard
            </Link>
          </div>
          {children}
        </div>
      </body>
    </html>
  );
}
