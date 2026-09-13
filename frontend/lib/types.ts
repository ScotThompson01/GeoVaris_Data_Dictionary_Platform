export type Client = { id:string; name:string; description:string|null; created_at:string; updated_at:string };
export type Project = { id:string; client_id:string; name:string; description:string|null; status:string; created_at:string; updated_at:string };

export type DictionaryField = {
  field_id: string;
  field_name: string;
  ordinal_position: number;

  native_data_type: string | null;
  normalized_data_type: string | null;

  is_nullable: boolean | null;
  is_primary_key: boolean;
  is_unique: boolean;

  source_object_id: string;
  object_name: string;
  object_type: string;

  data_source_id: string;
  data_source_name: string;
  source_type: string;
};

export type FieldGovernanceMetadata = {
  id: string | null;
  data_field_id: string;

  business_name: string | null;
  business_definition: string | null;
  department: string | null;
  data_owner: string | null;
  data_steward: string | null;
  business_process: string | null;
  system_of_record: string | null;

  is_cde: boolean;
  classification: string | null;
  approval_status: string;
  notes: string | null;

  created_at: string | null;
  updated_at: string | null;
};

export type FieldGovernanceUpdate = {
  business_name?: string | null;
  business_definition?: string | null;
  department?: string | null;
  data_owner?: string | null;
  data_steward?: string | null;
  business_process?: string | null;
  system_of_record?: string | null;

  is_cde?: boolean;
  classification?: string | null;
  approval_status?: string;
  notes?: string | null;
};