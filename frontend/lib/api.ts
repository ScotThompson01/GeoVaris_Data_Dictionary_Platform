import type { Client, DictionaryField, Project } from "./types";

const API_URL =
  typeof window === "undefined"
    ? process.env.INTERNAL_API_URL ?? "http://api:8000"
    : process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function parse<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(await r.text() || `Request failed: ${r.status}`);
  return r.json() as Promise<T>;
}
export async function getClients(){ return parse<Client[]>(await fetch(`${API_URL}/api/v1/clients`,{cache:"no-store"})); }
export async function getProjects(){ return parse<Project[]>(await fetch(`${API_URL}/api/v1/projects`,{cache:"no-store"})); }
export async function createClient(body:{name:string;description?:string}) {
  return parse<Client>(await fetch(`${API_URL}/api/v1/clients`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}));
}
export async function createProject(body:{client_id:string;name:string;description?:string;status?:string}) {
  return parse<Project>(await fetch(`${API_URL}/api/v1/projects`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...body,status:body.status??"active"})}));
}
export async function getDictionaryFields(
  search?: string,
): Promise<DictionaryField[]> {
  const params = new URLSearchParams();

  if (search?.trim()) {
    params.set("search", search.trim());
  }

  const query = params.toString();

  const url = query
    ? `${API_URL}/api/v1/dictionary?${query}`
    : `${API_URL}/api/v1/dictionary`;

  return parse<DictionaryField[]>(
    await fetch(url, {
      cache: "no-store",
    })
  );
}