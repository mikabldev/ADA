import os
import re
import html
import zipfile
import base64
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import yt_dlp
import streamlit as st

# -------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y RUTAS TEMPORALES
# -------------------------------------------------------------------
st.set_page_config(page_title="Amateur DJ Agent (ADA)", page_icon="🎧", layout="centered")

TEMP_DOWNLOADS_FOLDER = os.path.expanduser("~/Music/Descargas ADA Temp")
os.makedirs(TEMP_DOWNLOADS_FOLDER, exist_ok=True)

# -------------------------------------------------------------------
# PERSONALIZACIÓN VISUAL: VIDEO DE FONDO Y ESTILOS CSS
# -------------------------------------------------------------------
def obtener_video_local_base64(ruta_archivo):
    """
    Lee un archivo de video local y lo convierte a Base64.
    """
    if os.path.exists(ruta_archivo):
        with open(ruta_archivo, "rb") as video_file:
            bytes_video = video_file.read()
        return base64.b64encode(bytes_video).decode("utf-8")
    return None

RUTA_VIDEO_LOCAL = os.path.join("utils", "media", "fondo.mp4")
video_base64 = obtener_video_local_base64(RUTA_VIDEO_LOCAL)

if video_base64:
    fuente_video_html = f'<source src="data:video/mp4;base64,{video_base64}" type="video/mp4">'
else:
    # URL de respaldo si no existe el archivo local
    VIDEO_BG_URL = "https://assets.mixkit.co/videos/preview/mixkit-dj-hands-mixing-music-on-a-sound-console-41551-large.mp4"
    fuente_video_html = f'<source src="{VIDEO_BG_URL}" type="video/mp4">'

custom_css_and_video = f"""
<style>
/* Video de fondo a pantalla completa */
#bg-video {{
    position: fixed;
    right: 0;
    bottom: 0;
    min-width: 100%;
    min-height: 100%;
    z-index: -2;
    object-fit: cover;
    filter: brightness(0.35) contrast(1.1); /* Oscurece el video para dar legibilidad */
}}

/* Capa de degradado sobre el video */
.video-overlay {{
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(15, 15, 20, 0.65);
    z-index: -1;
}}

/* Fondo transparente en la estructura de Streamlit */
.stApp {{
    background: transparent;
}}

/* Personalización de tarjetas y contenedores */
div[data-testid="stVerticalBlock"] > div {{
    border-radius: 12px;
}}

/* Personalización de títulos */
h1 {{
    color: #00F0FF !important;
    text-shadow: 0 0 10px rgba(0, 240, 255, 0.5);
    font-family: 'Trebuchet MS', sans-serif;
}}

/* Botón principal estilo Cyberpunk / DJ */
div.stButton > button:first-child {{
    background: linear-gradient(135deg, #7928CA 0%, #FF0080 100%);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: bold;
    box-shadow: 0 4px 15px rgba(255, 0, 128, 0.4);
    transition: all 0.3s ease;
}}

div.stButton > button:first-child:hover {{
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(255, 0, 128, 0.6);
}}
</style>

<!-- Etiqueta HTML para reproducir el video de fondo -->
<video autoplay loop muted playsinline id="bg-video">
    {fuente_video_html}
</video>
<div class="video-overlay"></div>
"""

# Inyectar la personalización en la app
st.markdown(custom_css_and_video, unsafe_allow_html=True)

# -------------------------------------------------------------------
# MÓDULOS DE EXTRACCIÓN Y BÚSQUEDA
# -------------------------------------------------------------------

def obtener_metadatos_spotify(url_playlist):
    if "playlist/" in url_playlist:
        playlist_id = url_playlist.strip().split("playlist/")[1].split("?")[0]
    else:
        playlist_id = url_playlist.strip().split("?")[0]
        
    embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0.0.0 Safari/537.36'}
    
    try:
        response = requests.get(embed_url, headers=headers)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', id='resource')
        
        canciones = []
        if script_tag and script_tag.string:
            import json
            data = json.loads(script_tag.string)
            nombre_playlist = data.get('name', '').strip().lower()
            owner_data = data.get('owner', {})
            owner_name = owner_data.get('name', '').strip().lower() if isinstance(owner_data, dict) else ''
            
            for item in data.get('tracks', {}).get('items', []):
                track = item.get('track', item)
                titulo = track.get('name', '').strip()
                artistas = track.get('artists', [])
                artista = artistas[0].get('name', '').strip() if artistas else ""
                
                if not titulo or not artista:
                    continue
                    
                titulo = html.unescape(titulo)
                artista = html.unescape(artista)
                
                if (titulo.lower() == nombre_playlist or artista.lower() == owner_name or 
                    "spotify" in artista.lower() or "user" in artista.lower()):
                    continue
                    
                clave = f"{artista} - {titulo}"
                canciones.append({'query_limpia': clave, 'nombre_salida': clave})
                
        if canciones and ("spotify" in canciones[0]['query_limpia'].lower() or "user" in canciones[0]['query_limpia'].lower()):
            canciones = canciones[1:]
            
        return canciones
    except Exception:
        return []

def obtener_metadatos_ytdlp(url_input, plataforma):
    canciones = []
    url_limpia = url_input.split("?")[0].strip()
    
    if "on.soundcloud.com" in url_limpia:
        try:
            res_redir = requests.head(url_limpia, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
            url_limpia = res_redir.url.split("?")[0]
        except Exception:
            pass

    is_soundcloud = "soundcloud.com" in url_limpia.lower()
    
    opts = {
        'extract_flat': False if is_soundcloud else 'in_playlist',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True
    }
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            res = ydl.extract_info(url_limpia, download=False)
            
        entries = res.get('entries', []) if res else []
        if not entries and res:
            entries = [res]
            
        for entry in entries:
            if not entry: continue
            titulo = html.unescape(entry.get('title', '').strip())
            uploader = html.unescape((entry.get('uploader') or entry.get('channel') or entry.get('artist') or "Artista Desconocido").strip())
            if titulo:
                clave = titulo if " - " in titulo else f"{uploader} - {titulo}"
                url_cancion = entry.get('webpage_url') or entry.get('url')
                canciones.append({
                    'query_limpia': clave,
                    'nombre_salida': clave,
                    'url_directa': url_cancion if (url_cancion and url_cancion.startswith("http")) else None
                })
        return canciones
    except Exception:
        return []

def limpiar_texto(texto):
    return re.sub(r'[^\w\s]', '', texto).strip().lower()

def buscar_candidatos_multifuente(query):
    opts = {
        'quiet': True, 
        'no_warnings': True, 
        'ignoreerrors': True,
        'extract_flat': False, 
        'match_filter': yt_dlp.utils.match_filter_func('duration <= 600')
    }
    candidatos = []
    
    for prefix in ["scsearch3:", "ytsearch3:"]:
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                res = ydl.extract_info(f"{prefix}{query}", download=False)
                if res and res.get('entries'):
                    candidatos.extend([e for e in res['entries'] if e and (not e.get('duration') or e.get('duration') <= 600)])
            except Exception:
                pass
    return candidatos

def crear_archivo_zip(carpeta_origen, ruta_zip_salida):
    with zipfile.ZipFile(ruta_zip_salida, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(carpeta_origen):
            for file in files:
                if file.endswith('.wav'):
                    zipf.write(os.path.join(root, file), arcname=file)

# -------------------------------------------------------------------
# INTERFAZ GRÁFICA CON STREAMLIT
# -------------------------------------------------------------------
st.title("🎧 Amateur DJ Agent (ADA)")
st.caption("Convertidor y descargador inteligente de música a .WAV")

opcion = st.selectbox(
    "¿Qué deseas descargar?",
    [
        "Playlist de Spotify (URL pública)",
        "Playlist de YouTube (URL pública / no listada)",
        "Playlist de SoundCloud (URL pública / no listada)",
        "Una sola canción (SoundCloud / YouTube / Bandcamp)"
    ]
)

url_input = st.text_input("Ingresa la URL:", placeholder="https://...")

if st.button("🚀 Iniciar Procesamiento", type="primary"):
    if not url_input.strip():
        st.warning("Por favor, ingresa una URL válida.")
    else:
        # Limpiar descargas temporales previas
        for f in os.listdir(TEMP_DOWNLOADS_FOLDER):
            try:
                os.remove(os.path.join(TEMP_DOWNLOADS_FOLDER, f))
            except Exception:
                pass

        with st.spinner("°˖✧◝(⁰▿⁰)◜✧˖° Analizando enlace y metadatos..."):
            if "Spotify" in opcion:
                canciones = obtener_metadatos_spotify(url_input)
            elif "YouTube" in opcion:
                canciones = obtener_metadatos_ytdlp(url_input, "YouTube")
            elif "SoundCloud" in opcion:
                canciones = obtener_metadatos_ytdlp(url_input, "SoundCloud")
            else:
                canciones = obtener_metadatos_ytdlp(url_input, "Canción Única")

        if not canciones:
            st.error("(Ó╭╮Ò) No se pudieron identificar canciones en la URL proporcionada.")
        else:
            st.success(f"✓ Se identificaron **{len(canciones)}** canciones.")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            descargadas_ok = 0
            fallidas = 0
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'match_filter': yt_dlp.utils.match_filter_func('duration <= 600'),
                'add_metadata': True,
                'postprocessors': [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav', 'preferredquality': '192'},
                    {'key': 'FFmpegMetadata'}
                ],
                'outtmpl': os.path.join(TEMP_DOWNLOADS_FOLDER, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'noprogress': True,
            }

            for i, item in enumerate(canciones):
                query = item['query_limpia']
                nombre_archivo = re.sub(r'[\\/*?:"<>|]', "", item['nombre_salida'])
                status_text.text(f"Procesando [{i+1}/{len(canciones)}]: {nombre_archivo}")
                
                opts_item = dict(ydl_opts)
                opts_item['outtmpl'] = os.path.join(TEMP_DOWNLOADS_FOLDER, f'{nombre_archivo}.%(ext)s')
                
                descargada = False

                # Intento 1: URL directa
                if item.get('url_directa'):
                    try:
                        with yt_dlp.YoutubeDL(opts_item) as ydl:
                            ydl.download([item['url_directa']])
                        descargadas_ok += 1
                        descargada = True
                    except Exception:
                        pass

                # Fallback 1 & 2: Búsqueda multifuente si falla o no hay URL directa
                if not descargada:
                    candidatos = buscar_candidatos_multifuente(query)
                    if candidatos:
                        candidatos.sort(key=lambda x: fuzz.WRatio(limpiar_texto(query), limpiar_texto(x.get('title', ''))), reverse=True)
                        
                        for cand in candidatos[:3]:
                            url_cand = cand.get('webpage_url') or cand.get('url')
                            if url_cand:
                                try:
                                    with yt_dlp.YoutubeDL(opts_item) as ydl:
                                        ydl.download([url_cand])
                                    descargadas_ok += 1
                                    descargada = True
                                    break
                                except Exception:
                                    continue
                                    
                if not descargada:
                    fallidas += 1

                progress_bar.progress((i + 1) / len(canciones))

            status_text.text("¡Proceso completado!")
            
            st.divider()
            st.markdown("### 📊 RESUMEN FINAL DEL PROCESO")
            col1, col2, col3 = st.columns(3)
            col1.metric("♫ Detectadas", len(canciones))
            col2.metric("✦ Descargadas (.WAV)", descargadas_ok)
            col3.metric("♱ Fallidas", fallidas)

            if descargadas_ok > 0:
                zip_path = os.path.join(TEMP_DOWNLOADS_FOLDER, "compilado_dj_ada.zip")
                crear_archivo_zip(TEMP_DOWNLOADS_FOLDER, zip_path)
                
                with open(zip_path, "rb") as f:
                    st.download_button(
                        label="📦 Descargar todo (.ZIP)",
                        data=f,
                        file_name="compilado_dj_ada.zip",
                        mime="application/zip",
                        type="primary"
                    )