"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import FieldGovernancePanel from "../../../../../../components/FieldGovernancePanel";
import FieldTechnicalMetadataPanel from "../../../../../../components/FieldTechnicalMetadataPanel";
import FieldProfilingPanel from "../../../../../../components/FieldProfilingPanel";
import FieldQualityDashboard from "../../../../../../components/FieldQualityDashboard";

import {
  getDictionaryFields,
  getProjects,
} from "../../../../../../lib/api";

import type {
  DictionaryField,
  Project,
} from "../../../../../../lib/types";

type SelectedField = {
  project: Project;
  field: DictionaryField;
};

export default function FieldGovernancePage() {
  const params = useParams<{
    projectId: string;
    fieldId: string;
  }>();

  const router = useRouter();
  const { projectId, fieldId } = params;

  const [selection, setSelection] =
    useState<SelectedField | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;

    setLoading(true);
    setSelection(null);
    setMessage("");

    async function loadField() {
      try {
        const projects = await getProjects();

        if (!active) return;

        const project = projects.find(
          (item) => item.id === projectId,
        );

        if (!project) {
          setMessage("Project unavailable.");
          return;
        }

        const fields = await getDictionaryFields(
          projectId,
          "",
          {},
        );

        if (!active) return;

        const field = fields.find(
          (item) => item.field_id === fieldId,
        );

        if (!field) {
          setMessage("Field unavailable.");
          return;
        }

        setSelection({ project, field });
      } catch {
        if (active) {
          setMessage("Unable to load field information.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadField();

    return () => {
      active = false;
    };
  }, [projectId, fieldId]);

  return (
    <>
      <section className="card">
        <Link href="/dictionary/all-fields">
          Back to Data Dictionary
        </Link>

        <p className="eyebrow">FIELD GOVERNANCE</p>

        <h1>
          {selection?.field.field_name ?? "Field Governance"}
        </h1>

        {selection && (
          <p>
            {selection.project.name}
            {" / "}
            {selection.field.data_source_name}
            {" / "}
            {selection.field.object_name}
          </p>
        )}
      </section>

      {loading && <p>Loading field information...</p>}

      {message && <p role="alert">{message}</p>}

      {!loading && selection && (
        <div className="field-governance-workspace">
          <FieldQualityDashboard
            key={selection.field.field_id}
            field={selection.field}
          />

          <FieldGovernancePanel
            key={selection.field.field_id}
            field={selection.field}
            clientId={selection.project.client_id}
            onClose={() => router.push("/dictionary/all-fields")}
          />

          <FieldTechnicalMetadataPanel
            field={selection.field}
          />

          <FieldProfilingPanel
            field={selection.field}
          />
        </div>
      )}
    </>
  );
}
