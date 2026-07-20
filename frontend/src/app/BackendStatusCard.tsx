import { useEffect, useState } from "react";

type BackendStatus = "connecting" | "online" | "unavailable";

export function BackendStatusCard({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [status, setStatus] = useState<BackendStatus>("connecting");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    void fetch(`${apiBaseUrl.replace(/\/$/, "")}/api/v1/health`)
      .then((response) => response.ok ? response.json() : null)
      .then((body: { status?: string } | null) => { if (!cancelled) setStatus(body?.status === "ok" ? "online" : "unavailable"); })
      .catch(() => { if (!cancelled) setStatus("unavailable"); });
    return () => { cancelled = true; };
  }, [apiBaseUrl, attempt]);
  const label = status === "online" ? "Backend online" : status === "connecting" ? "Connecting to local backend…" : "Backend unavailable";
  return <span className={`connection connection--${status}`}>{label}{status === "unavailable" && <button type="button" onClick={() => setAttempt((item) => item + 1)}>Retry</button>}</span>;
}
