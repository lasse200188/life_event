"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { createPlan } from "@/lib/api";

type EmploymentType =
  | "employed"
  | "self_employed"
  | "mixed"
  | "student"
  | "unemployed";

type InsuranceType = "public" | "private" | "both" | "none";

export default function OnboardingPage() {
  const router = useRouter();
  const [birthDate, setBirthDate] = useState("");
  const [employmentType, setEmploymentType] = useState<EmploymentType>("employed");
  const [married, setMarried] = useState(false);
  const [insuranceType, setInsuranceType] = useState<InsuranceType>("public");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = useMemo(() => birthDate.length > 0 && !isSubmitting, [birthDate, isSubmitting]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    const facts: Record<string, unknown> = {
      birth_date: birthDate,
      employment_type: employmentType,
      married,
      ...(insuranceType !== "none"
        ? {
            public_insurance: insuranceType === "public" || insuranceType === "both",
            private_insurance: insuranceType === "private" || insuranceType === "both",
          }
        : {}),
    };

    try {
      const result = await createPlan({
        template_key: "birth_de/v2",
        facts,
      });
      router.push(`/app/plan/${result.id}`);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Plan konnte nicht erstellt werden");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main>
      <h1>Onboarding: Angaben zur Geburt</h1>
      <p>Diese Eingaben werden als Facts an die Plan-Engine gesendet.</p>

      <form className="card" onSubmit={onSubmit} style={{ display: "grid", gap: "0.8rem" }}>
        <label>
          Geburtsdatum
          <input
            required
            type="date"
            value={birthDate}
            onChange={(event) => setBirthDate(event.target.value)}
            style={{ display: "block", marginTop: "0.25rem", width: "100%", padding: "0.5rem" }}
          />
        </label>

        <label>
          Beschaeftigungsart
          <select
            value={employmentType}
            onChange={(event) => setEmploymentType(event.target.value as EmploymentType)}
            style={{ display: "block", marginTop: "0.25rem", width: "100%", padding: "0.5rem" }}
          >
            <option value="employed">Angestellt</option>
            <option value="self_employed">Selbststaendig</option>
            <option value="mixed">Gemischt</option>
            <option value="student">Studierend</option>
            <option value="unemployed">Ohne Beschaeftigung</option>
          </select>
        </label>

        <label>
          <input
            type="checkbox"
            checked={married}
            onChange={(event) => setMarried(event.target.checked)}
            style={{ marginRight: "0.45rem" }}
          />
          Verheiratet
        </label>

        <fieldset style={{ border: "1px solid #d9d5c8", borderRadius: "10px", padding: "0.75rem" }}>
          <legend>Versicherung</legend>
          <label style={{ display: "block" }}>
            <input
              type="radio"
              name="insurance"
              value="public"
              checked={insuranceType === "public"}
              onChange={() => setInsuranceType("public")}
            />{" "}
            Gesetzlich
          </label>
          <label style={{ display: "block" }}>
            <input
              type="radio"
              name="insurance"
              value="private"
              checked={insuranceType === "private"}
              onChange={() => setInsuranceType("private")}
            />{" "}
            Privat
          </label>
          <label style={{ display: "block" }}>
            <input
              type="radio"
              name="insurance"
              value="both"
              checked={insuranceType === "both"}
              onChange={() => setInsuranceType("both")}
            />{" "}
            Beide
          </label>
          <label style={{ display: "block" }}>
            <input
              type="radio"
              name="insurance"
              value="none"
              checked={insuranceType === "none"}
              onChange={() => setInsuranceType("none")}
            />{" "}
            Keine Angabe
          </label>
        </fieldset>

        {error ? <p style={{ color: "#b01b2e", margin: 0 }}>{error}</p> : null}

        <button className="button button-primary" type="submit" disabled={!canSubmit}>
          {isSubmitting ? "Erzeuge Plan ..." : "Plan erzeugen"}
        </button>
      </form>
    </main>
  );
}
