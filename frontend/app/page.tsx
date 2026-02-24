import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <h1>Life Event</h1>
      <p>Milestone 4 Einstiegspunkte.</p>
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <Link className="button button-primary" href="/events/geburt">
          Zu /events/geburt
        </Link>
        <Link className="button button-ghost" href="/app/onboarding">
          Zu /app/onboarding
        </Link>
      </div>
    </main>
  );
}
