import Image from "next/image";
import Link from "next/link";
export default function Sidebar(){
  return <aside className="sidebar">
    <div className="brand">
      <Image src="/branding/geovaris-logo.svg" alt="GeoVaris" width={82} height={82} className="logo" priority />
      <div><strong>GeoVaris</strong><span>Data Dictionary Platform</span></div>
    </div>
    <nav>
      <Link href="/">Dashboard</Link>
      <Link href="/clients">Clients</Link>
      <Link href="/projects">Projects</Link>
      <div className="disabled">Data Sources <small>Soon</small></div>
      <div className="disabled">Data Dictionary <small>Soon</small></div>
      <div className="disabled">Data Quality <small>Soon</small></div>
    </nav>
  </aside>;
}
