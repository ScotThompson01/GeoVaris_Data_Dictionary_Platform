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