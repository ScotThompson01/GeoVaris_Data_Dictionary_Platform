export type Client = { id:string; name:string; description:string|null; created_at:string; updated_at:string };
export type Project = { id:string; client_id:string; name:string; description:string|null; status:string; created_at:string; updated_at:string };
