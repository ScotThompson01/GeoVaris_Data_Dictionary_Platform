"use client";
import {FormEvent,useState} from "react";
import {createClient} from "../lib/api";
export default function ClientForm({onCreated}:{onCreated?:()=>void}){
  const [name,setName]=useState(""); const [description,setDescription]=useState(""); const [msg,setMsg]=useState("");
  async function submit(e:FormEvent){e.preventDefault();setMsg("Saving...");
    try{await createClient({name,description});setName("");setDescription("");setMsg("Client created.");onCreated?.();}
    catch(err){setMsg(err instanceof Error?err.message:"Unable to create client.");}}
  return <form className="form" onSubmit={submit}>
    <label>Client name<input value={name} onChange={e=>setName(e.target.value)} required/></label>
    <label>Description<textarea value={description} onChange={e=>setDescription(e.target.value)}/></label>
    <button>Create client</button>{msg&&<p className="notice">{msg}</p>}
  </form>;
}
