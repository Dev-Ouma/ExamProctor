export type Mode = "staging" | "live";

export function StagingBanner({ mode }: { mode: Mode }) {
  if (mode !== "staging") {
    return null;
  }
  return (
    <div role="status" style={{ background: "#ff7f50", color: "#000", padding: "8px 16px" }}>
      Staging environment: synthetic data only
    </div>
  );
}

export function App({ mode }: { mode: Mode }) {
  return (
    <>
      <StagingBanner mode={mode} />
      <main style={{ padding: 16 }}>
        <h1>ExamProctor</h1>
        <p>Live wall and review dashboards arrive in M5 and M6.</p>
      </main>
    </>
  );
}
