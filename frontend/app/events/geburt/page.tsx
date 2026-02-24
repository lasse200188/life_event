import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Geburt: Fristen und To-dos im Ueberblick",
  description:
    "Checkliste fuer Geburt in Deutschland: Kindergeld, Elterngeld, Krankenkasse und weitere Fristen einfach planen.",
};

export default function BirthEventLandingPage() {
  return (
    <main>
      <section className="card" style={{ padding: "1.5rem" }}>
        <p style={{ margin: 0, color: "#5b665f", fontWeight: 700 }}>Event Guide</p>
        <h1 style={{ marginTop: "0.5rem", marginBottom: "0.75rem" }}>
          Geburt: Was in den ersten Wochen wichtig ist
        </h1>
        <p style={{ marginTop: 0, lineHeight: 1.55 }}>
          Nach der Geburt fallen viele Fristen gleichzeitig an. Wir erstellen aus deinen Angaben
          einen klaren Plan mit Aufgaben, Prioritaeten und Deadlines.
        </p>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <Link className="button button-primary" href="/app/onboarding">
            Jetzt Plan starten
          </Link>
          <Link className="button button-ghost" href="/">
            Zur Startseite
          </Link>
        </div>
      </section>

      <section style={{ marginTop: "1rem", display: "grid", gap: "0.8rem" }}>
        <article className="card">
          <h2>Typische Aufgaben</h2>
          <ul>
            <li>Geburtsurkunde beantragen</li>
            <li>Kindergeld beantragen</li>
            <li>Elterngeld beantragen</li>
            <li>Kind bei der Krankenversicherung anmelden</li>
            <li>Elternzeit beim Arbeitgeber anmelden</li>
          </ul>
        </article>

        <article className="card">
          <h2>Vorteile der Plattform</h2>
          <ul>
            <li>Ein zentraler Plan statt verstreuter Notizen</li>
            <li>Fristen und Prioritaeten auf einen Blick</li>
            <li>Fortschritt laufend sichtbar</li>
          </ul>
        </article>
      </section>
    </main>
  );
}
