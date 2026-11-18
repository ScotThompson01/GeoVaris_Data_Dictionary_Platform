"use client";

import { useEffect, useState } from "react";
import { getFieldProfilingResults } from "../lib/api";
import { calculateObservedCompleteness } from "../lib/field-quality-metrics";
import type { DictionaryField, ProfilingResult } from "../lib/types";

type Props = {
  field: DictionaryField;
};

export default function FieldQualityDashboard({ field }: Props) {
  const [profile, setProfile] = useState<ProfilingResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;

    setProfile(null);
    setLoading(true);
    setMessage("");

    async function load() {
      try {
        const results = await getFieldProfilingResults(field.field_id);

        if (active) {
          setProfile(
            results.find(
              (result) => result.data_field_id === field.field_id,
            ) ?? null,
          );
        }
      } catch {
        if (active) {
          setMessage("Unable to load profiling measurements.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [field.field_id]);

  const completeness = calculateObservedCompleteness(
    profile?.data_field_id === field.field_id ? profile : null,
  );

  return (
    <section className="card">
      <h2>Data Quality Dashboard</h2>

      <p>
        Field-level quality measurements and observed data characteristics.
      </p>

      {loading && <p>Loading measurements...</p>}
      {message && <p role="alert">{message}</p>}

      <div className="field-quality-grid">
        <article className="field-quality-metric">
          <h3>Overall Data Quality</h3>
          <strong>Not measured</strong>
        </article>

        <article className="field-quality-metric">
          <h3>Observed Completeness</h3>

          <strong>
            {loading
              ? "Loading..."
              : completeness
                ? `${completeness.percentage.toFixed(2)}%`
                : "Not measured"}
          </strong>

          {!loading && completeness && (
            <>
              <progress
                max={100}
                value={completeness.percentage}
                aria-label="Observed completeness"
                style={{
                  width: "100%",
                  accentColor: "var(--p)",
                  marginTop: "12px",
                }}
              />

              <p className="field-subtext">
                {completeness.populatedCount.toLocaleString()}
                {" / "}
                {completeness.rowCount.toLocaleString()}
                {" non-null values"}
              </p>

              <p className="field-subtext">
                Null values: {completeness.nullCount.toLocaleString()}
              </p>
            </>
          )}
        </article>

        {[
          "Validity",
          "Uniqueness",
          "Consistency",
          "Accuracy",
          "Timeliness",
        ].map((dimension) => (
          <article className="field-quality-metric" key={dimension}>
            <h3>{dimension}</h3>
            <strong>Not measured</strong>
          </article>
        ))}
      </div>

      {!loading && completeness && (
        <p className="field-subtext">
          Profile created:{" "}
          {new Date(completeness.measuredAt).toLocaleString()}
        </p>
      )}

      <p className="field-subtext">
        Observed completeness measures non-null values from a previous
        profile. It does not establish compliance with approved
        business rules.
      </p>

      <p className="field-subtext">
        Accuracy requires validation against a trusted reference source.
      </p>
    </section>
  );
}
