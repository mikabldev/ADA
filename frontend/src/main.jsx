import React, {useEffect, useState} from "react";
import {createRoot} from "react-dom/client";
import "./style.css";

const API = import.meta.env.VITE_API_URL || "/api/v1";
const qualities = ["WAV 16-bit / 44.1 kHz", "WAV 24-bit / 48 kHz"];

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {headers: {"Content-Type": "application/json"}, ...options});
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.map((x) => x.msg).join("; ") : body.detail;
    throw new Error(detail || `Error HTTP ${response.status}`);
  }
  return response.json();
}

function App() {
  const [platform, setPlatform] = useState("spotify");
  const [url, setUrl] = useState("");
  const [tracks, setTracks] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [quality, setQuality] = useState(qualities[1]);
  const [phase, setPhase] = useState("initial");
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!job || !["pending", "running"].includes(job.status)) return;
    const timer = setTimeout(async () => {
      try {
        const fresh = await request(`/jobs/${job.id}`);
        setJob(fresh);
        if (fresh.status === "completed") setPhase("completed");
        else if (["failed", "cancelled"].includes(fresh.status)) setPhase("error");
        else if (fresh.status === "expired") setPhase("expired");
      } catch (e) { setError(e.message); setPhase("error"); }
    }, 1000);
    return () => clearTimeout(timer);
  }, [job]);

  async function analyze(event) {
    event.preventDefault(); setError(""); setPhase("analyzing"); setJob(null);
    try {
      const data = await request("/analyze", {method: "POST", body: JSON.stringify({platform, url})});
      setTracks(data.tracks); setSelected(new Set(data.tracks.map((t) => t.id))); setPhase("results");
    } catch (e) { setError(e.message); setPhase("error"); }
  }

  function toggle(id) {
    setSelected((current) => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next; });
  }

  async function start() {
    setError("");
    try {
      const chosen = tracks.filter((track) => selected.has(track.id));
      if (!chosen.length) throw new Error("Selecciona al menos una canción");
      const created = await request("/jobs", {method: "POST", body: JSON.stringify({tracks: chosen, quality})});
      setJob(created); setPhase("downloading");
    } catch (e) { setError(e.message); setPhase("error"); }
  }

  const reset = () => { setTracks([]); setSelected(new Set()); setJob(null); setError(""); setPhase("initial"); };

  return <main>
    <header><span className="eyebrow">Amateur DJ Agent</span><h1>Prepara tus pistas, sin perder el ritmo.</h1><p>Analiza enlaces públicos, elige canciones y descarga un ZIP con tus WAV.</p></header>
    <section className="card" aria-live="polite">
      <nav className="steps" aria-label="Progreso"><b className={phase !== "initial" ? "done" : ""}>1 Analizar</b><b className={tracks.length ? "done" : ""}>2 Seleccionar</b><b className={job ? "done" : ""}>3 Descargar</b></nav>
      {!["downloading", "completed", "expired"].includes(phase) && <form onSubmit={analyze}>
        <label>Plataforma<select value={platform} onChange={(e) => setPlatform(e.target.value)}><option value="spotify">Spotify</option><option value="youtube">YouTube</option><option value="soundcloud">SoundCloud</option><option value="bandcamp">Bandcamp</option></select></label>
        <label>URL pública<input type="url" required placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)}/></label>
        <button disabled={phase === "analyzing"}>{phase === "analyzing" ? "Analizando…" : "Analizar URL"}</button>
      </form>}
      {tracks.length > 0 && !job && <div className="results"><div className="resultHead"><h2>{tracks.length} canciones detectadas</h2><button className="ghost" onClick={() => setSelected(selected.size ? new Set() : new Set(tracks.map(t => t.id)))}>{selected.size ? "Excluir todas" : "Seleccionar todas"}</button></div>
        <ul>{tracks.map((track) => <li key={track.id}><label><input type="checkbox" checked={selected.has(track.id)} onChange={() => toggle(track.id)}/><span><strong>{track.title || track.output_name}</strong><small>{track.artist || "Artista desconocido"}</small></span></label></li>)}</ul>
        <label>Calidad WAV<select value={quality} onChange={(e) => setQuality(e.target.value)}>{qualities.map(q => <option key={q}>{q}</option>)}</select></label>
        <button onClick={start}>Descargar {selected.size} seleccionadas</button></div>}
      {job && <div className="job"><h2>{phase === "completed" ? "Tu ZIP está listo" : phase === "expired" ? "El trabajo expiró" : "Procesando canciones"}</h2><progress max="100" value={job.progress}/><p>{job.progress}% · {job.status}</p>
        {job.results?.length > 0 && <ul>{job.results.map((r) => <li key={r.track_id}><strong>{r.status}</strong> {r.message}</li>)}</ul>}
        {phase === "completed" && <a className="button" href={`${API}/jobs/${job.id}/download`}>Descargar ZIP</a>}
        {["completed", "expired", "error"].includes(phase) && <button className="ghost" onClick={reset}>Empezar de nuevo</button>}
      </div>}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
    <footer>Usa únicamente contenido que tengas derecho a descargar y respeta los términos de cada plataforma.</footer>
  </main>;
}

createRoot(document.getElementById("root")).render(<App/>);
