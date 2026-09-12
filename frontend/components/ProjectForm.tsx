"use client";
import {FormEvent,useEffect,useState} from "react";
import {createProject,getClients} from "../lib/api";
import type {Client} from "../lib/types";
export default function ProjectForm({onCreated}:{onCreated?:()=>void}){
  const [clients,setClients]=useState<Client[]>([]);const [clientId,setClientId]=useState("");const [name,setName]=useState("");const [description,setDescription]=useState("");const [msg,setMsg]=useState("");
  useEffect(()=>{getClients().then(x=>{setClients(x);if(x[0])setClientId(x[0].id)}).catch(()=>setMsg("Unable to load clients."));},[]);
  async function submit(e:FormEvent){e.preventDefault();setMsg("Saving...");
    try{await createProject({client_id:clientId,name,description,status:"active"});setName("");setDescription("");setMsg("Project created.");onCreated?.();}
    catch(err){setMsg(err instanceof Error?err.message:"Unable to create project.");}}
  return <form className="form" onSubmit={submit}>
    <label>Client<select value={clientId} onChange={e=>setClientId(e.target.value)} required>{clients.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
    <label>Project name<input value={name} onChange={e=>setName(e.target.value)} required/></label>
    <label>Description<textarea value={description} onChange={e=>setDescription(e.target.value)}/></label>
    <button disabled={!clientId}>Create project</button>{msg&&<p className="notice">{msg}</p>}
  </form>;
}
