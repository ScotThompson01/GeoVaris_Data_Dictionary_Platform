"use client";

import { useEffect, useState } from "react";

import { getFieldProfilingResults } from "../lib/api";
import type {
  DictionaryField,
  ProfilingResult,
} from "../lib/types";

type Props = {
  field: DictionaryField;
};

function displayValue(value: string | number | null): string {
  return value === null ? "Not available" : String(value);
}

function displayPercentage(value: string): string {
  const percentage = Number(value);

  return Number.isFinite(percentage)
    ? `${percentage.toFixed(2)}%`
    : "Not available";
}

export default function FieldProfilingPanel({ field }: Props) {
  const [result, setResult] = useState<ProfilingResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;

    setResult(null);
    setLoading(true);
    setMessage("");

    async function load() {
      try {
        const results = await getFieldProfilingResults(field.field_id);

        if (!active) {
          return;
        }

        setResult(results[0] ?? null);
      } catch {
        if (active) {
          setMessage("Unable to load profiling results.");
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

  return (
    <section className="card">
      <h2>Observed Data Profile</h2>

      <p>
        Measurements from a previous scan of{" "}
        <strong>{field.field_name}</strong>. These are observed
        values, not approved Data Quality standards.
      </p>

      {loading && <p>Loading profiling results...</p>}

      {!loading && message && (
        <p role="alert">{message}</p>
      )}

      {!loading && !message && !result && (
        <p>No profiling results are available for this field.</p>
      )}

      {!loading && !message && result && (
        <>
          <p>
            <strong>Profile created:</strong>{" "}
            {new Date(result.created_at).toLocaleString()}
          </p>

          <dl>
            <dt>Rows profiled</dt>
            <dd>{displayValue(result.row_count)}</dd>

            <dt>Null count</dt>
            <dd>{displayValue(result.null_count)}</dd>

            <dt>Null percentage</dt>
            <dd>{displayPercentage(result.null_percentage)}</dd>

            <dt>Distinct count</dt>
            <dd>{displayValue(result.distinct_count)}</dd>

            <dt>Distinct percentage</dt>
            <dd>{displayPercentage(result.distinct_percentage)}</dd>

            <dt>Observed minimum</dt>
            <dd>{displayValue(result.minimum_value)}</dd>

            <dt>Observed maximum</dt>
            <dd>{displayValue(result.maximum_value)}</dd>

            <dt>Minimum string length</dt>
            <dd>{displayValue(result.minimum_length)}</dd>

            <dt>Maximum string length</dt>
            <dd>{displayValue(result.maximum_length)}</dd>
          </dl>
        </>
      )}
    </section>
  );
}