import os
import re
import html
import io
import zipfile
import base64
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import yt_dlp
import streamlit as st

# -------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y RUTA DE DESCARGAS
# -------------------------------------------------------------------
st.set_page_config(page_title="Amateur DJ Agent (ADA)", page_icon="🎧", layout="centered")

DOWNLOADS_FOLDER = os.path.expanduser("~/Music/Descargas ADA")
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

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
# MÓDULO 1: EXTRACCIÓN DE METADATOS
# -------------------------------------------------------------------

def decodificar_texto(texto):
    """
    Decodifica entidades HTML y secuencias de escape unicode (ej: \\u003c3, \\u00f8).
    """
    if not texto:
        return ""
    t = html.unescape(str(texto))
    try:
        if "\\u" in t:
            t = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), t)
    except Exception:
        pass
    return t.strip()

def obtener_metadatos_spotify(url_playlist):
    """
    Extrae los metadatos de una playlist pública de Spotify decodificando caracteres Unicode
    y filtrando estrictamente la cabecera de la lista.
    Utiliza la API web de Spotify con token anónimo oficial y fallback a embed HTML con cabeceras completas.
    """
    if "playlist/" in url_playlist:
        playlist_id = url_playlist.strip().split("playlist/")[1].split("?")[0]
    else:
        playlist_id = url_playlist.strip().split("?")[0]

    headers_browser = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        'Referer': 'https://open.spotify.com/',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
    }

    canciones = []

    # 1. INTENTO 1: API Oficial de Spotify con Token Web Anónimo (Evita HTTP 403)
    try:
        token_res = requests.get("https://open.spotify.com/get_access_token", headers=headers_browser, timeout=10)
        if token_res.status_code == 200:
            token_data = token_res.json()
            access_token = token_data.get("accessToken")
            if access_token:
                api_headers = {
                    'Authorization': f'Bearer {access_token}',
                    'User-Agent': headers_browser['User-Agent']
                }
                api_url = f"https://api.spotify.com/v1/playlists/{playlist_id}?fields=name,owner,tracks.items(track(name,artists(name)))"
                api_res = requests.get(api_url, headers=api_headers, timeout=10)
                if api_res.status_code == 200:
                    api_json = api_res.json()
                    nombre_playlist = decodificar_texto(api_json.get('name', '')).lower()
                    tracks_items = api_json.get('tracks', {}).get('items', [])
                    for item in tracks_items:
                        track = item.get('track')
                        if not track or not isinstance(track, dict):
                            continue
                        titulo = decodificar_texto(track.get('name', ''))
                        artistas = track.get('artists', [])
                        artista = decodificar_texto(artistas[0].get('name', '')) if artistas else ""
                        
                        if not titulo or not artista or titulo.lower() == nombre_playlist:
                            continue
                            
                        clave = f"{artista} - {titulo}"
                        canciones.append({
                            'query_limpia': clave,
                            'nombre_salida': clave
                        })
                    if canciones:
                        return canciones
    except Exception:
        pass

    # 2. INTENTO 2: Embed HTML con cabeceras de navegador completas
    embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
    try:
        response = requests.get(embed_url, headers=headers_browser, timeout=10)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        meta_title = soup.find('meta', property='og:title')
        nombre_playlist_meta = decodificar_texto(meta_title['content']).lower() if meta_title and meta_title.get('content') else ""
        
        meta_creator = soup.find('meta', property='music:creator') or soup.find('meta', name='author')
        creador_playlist_meta = decodificar_texto(meta_creator['content']).lower() if meta_creator and meta_creator.get('content') else ""
        
        script_tag = soup.find('script', id='resource') or soup.find('script', id='initial-state') or soup.find('script', id='__NEXT_DATA__')
        
        if script_tag and script_tag.string:
            import json
            try:
                data = json.loads(script_tag.string)
                if 'props' in data and 'pageProps' in data.get('props', {}):
                    data = data['props']['pageProps'].get('state', {}).get('data', {}).get('entity', data)
                    
                nombre_playlist = decodificar_texto(data.get('name', '') or data.get('title', '')).lower() or nombre_playlist_meta
                owner_data = data.get('owner', {})
                owner_name = decodificar_texto(owner_data.get('name', '') or owner_data.get('display_name', '') or owner_data.get('id', '')).lower() if isinstance(owner_data, dict) else creador_playlist_meta
                
                tracks = data.get('tracks', {}).get('items', []) if isinstance(data.get('tracks'), dict) else (data.get('trackList') or [])
                
                for item in tracks:
                    track = item.get('track', item)
                    if not isinstance(track, dict):
                        continue
                        
                    titulo = decodificar_texto(track.get('name', '') or track.get('title', ''))
                    artistas = track.get('artists', [])
                    if isinstance(artistas, list) and artistas:
                        if isinstance(artistas[0], dict):
                            artista = decodificar_texto(artistas[0].get('name', ''))
                        else:
                            artista = decodificar_texto(str(artistas[0]))
                    else:
                        artista = decodificar_texto(track.get('subtitle', '') or track.get('artist', ''))
                    
                    if not titulo or not artista:
                        continue
                    
                    t_low = titulo.lower()
                    a_low = artista.lower()
                    
                    if (t_low == nombre_playlist or t_low == nombre_playlist_meta or 
                        (a_low == owner_name and t_low == nombre_playlist) or 
                        (a_low == creador_playlist_meta and t_low == nombre_playlist) or
                        a_low in ["spotify", "user", "playlist"]):
                        continue
                        
                    clave = f"{artista} - {titulo}"
                    canciones.append({
                        'query_limpia': clave,
                        'nombre_salida': clave
                    })
            except Exception:
                pass

        if not canciones:
            matches = re.findall(r'"title":"([^"]+)".*?"subtitle":"([^"]+)"', response.text)
            for idx, (titulo, artista) in enumerate(matches):
                titulo_clean = decodificar_texto(titulo)
                artista_clean = decodificar_texto(artista)
                
                t_low = titulo_clean.lower()
                a_low = artista_clean.lower()
                
                if idx == 0 and (t_low == nombre_playlist_meta or a_low in ["spotify", "user", "playlist"] or len(matches) > 1):
                    continue
                    
                if (t_low == nombre_playlist_meta or 
                    (creador_playlist_meta and a_low == creador_playlist_meta) or 
                    a_low in ["spotify", "user", "playlist"]):
                    continue
                    
                clave = f"{artista_clean} - {titulo_clean}"
                canciones.append({
                    'query_limpia': clave,
                    'nombre_salida': clave
                })

        return canciones
    except Exception:
        return []

def obtener_metadatos_ytdlp(url_playlist, plataforma="YouTube / SoundCloud"):
    """
    Extrae los metadatos de playlists de SoundCloud/YouTube soportando
    sets públicos de SoundCloud, URLs acortadas y parámetros de rastreo.
    """
    canciones = []
    url_limpia = url_playlist.split("?")[0].strip()
    
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
        'skip_download': True,
        'extractor_args': {
            'youtube': {'player_client': ['android', 'ios', 'web']}
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            res = ydl.extract_info(url_limpia, download=False)
            
        entries = res.get('entries', []) if res else []
        if not entries and res:
            entries = [res]
            
        for entry in entries:
            if not entry:
                continue
            titulo = decodificar_texto(entry.get('title', '').strip())
            uploader = decodificar_texto((entry.get('uploader') or entry.get('channel') or entry.get('artist') or "Artista Desconocido").strip())
            
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

def obtener_metadatos_cancion_unica(url_cancion):
    """
    Extrae los metadatos de 1 sola canción desde SoundCloud, YouTube o Bandcamp.
    """
    url_limpia = url_cancion.split("?")[0].strip()
    
    if "on.soundcloud.com" in url_limpia:
        try:
            res_redir = requests.head(url_limpia, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
            url_limpia = res_redir.url.split("?")[0]
        except Exception:
            pass

    opts = {
        'quiet': True, 
        'no_warnings': True, 
        'skip_download': True,
        'extractor_args': {
            'youtube': {'player_client': ['android', 'ios', 'web']}
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            res = ydl.extract_info(url_limpia, download=False)
            
        if not res:
            return []
            
        titulo = decodificar_texto(res.get('title', '').strip())
        uploader = decodificar_texto((res.get('uploader') or res.get('channel') or res.get('artist') or "Artista Desconocido").strip())
        
        clave = titulo if " - " in titulo else f"{uploader} - {titulo}"
        return [{
            'query_limpia': clave,
            'nombre_salida': clave,
            'url_directa': url_limpia
        }]
    except Exception:
        return []

# -------------------------------------------------------------------
# MÓDULO 2: BÚSQUEDA Y ANÁLISIS MULTIFUENTE
# -------------------------------------------------------------------

def limpiar_texto(texto):
    t = re.sub(r'[^\w\s]', ' ', texto)
    return ' '.join(t.split()).lower()

def calcular_similitud(query, titulo_cand, uploader=""):
    q_clean = limpiar_texto(query)
    t_clean = limpiar_texto(titulo_cand)
    u_clean = limpiar_texto(uploader)
    
    score_token_set = fuzz.token_set_ratio(q_clean, t_clean)
    score_token_sort = fuzz.token_sort_ratio(q_clean, t_clean)
    score_wratio = fuzz.WRatio(q_clean, t_clean)
    score_titulo = max(score_token_set, score_token_sort, score_wratio)
    
    combo_cand = f"{u_clean} {t_clean}".strip()
    score_combo_set = fuzz.token_set_ratio(q_clean, combo_cand)
    score_combo_sort = fuzz.token_sort_ratio(q_clean, combo_cand)
    score_combo_wratio = fuzz.WRatio(q_clean, combo_cand)
    score_combo = max(score_combo_set, score_combo_sort, score_combo_wratio)
    
    return max(score_titulo, score_combo)

def buscar_candidatos_multifuente(query):
    """
    Busca candidatos dando prioridad a SoundCloud y silenciando warnings.
    """
    opts = {
        'quiet': True, 
        'no_warnings': True, 
        'ignoreerrors': True,
        'extract_flat': False, 
        'match_filter': yt_dlp.utils.match_filter_func('duration <= 600'),
        'extractor_args': {
            'youtube': {'player_client': ['android', 'ios', 'web']}
        }
    }
    candidatos = []
    
    def es_track_valido(cand):
        if not cand:
            return False
        dur = cand.get('duration')
        if dur and dur > 600:
            return False
        return True

    # 1. SoundCloud (Prioridad)
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            res_sc = ydl.extract_info(f"scsearch3:{query}", download=False)
            if res_sc and res_sc.get('entries'):
                for e in res_sc['entries']:
                    if es_track_valido(e):
                        candidatos.append(e)
        except Exception:
            pass

    # 2. YouTube
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            res_yt = ydl.extract_info(f"ytsearch3:{query}", download=False)
            if res_yt and res_yt.get('entries'):
                for e in res_yt['entries']:
                    if es_track_valido(e):
                        candidatos.append(e)
        except Exception:
            pass

    return candidatos

def crear_zip_en_memoria(rutas_archivos):
    """
    Empaqueta los archivos descargados en un ZIP almacenado en memoria RAM (io.BytesIO)
    para evitar duplicar archivos y espacio en el disco duro.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for ruta in rutas_archivos:
            if os.path.exists(ruta):
                zipf.write(ruta, arcname=os.path.basename(ruta))
    buffer.seek(0)
    return buffer

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
        with st.spinner("°˖✧◝(⁰▿⁰)◜✧˖° Analizando enlace y metadatos..."):
            if "Spotify" in opcion:
                canciones = obtener_metadatos_spotify(url_input)
            elif "YouTube" in opcion:
                canciones = obtener_metadatos_ytdlp(url_input, "YouTube")
            elif "SoundCloud" in opcion:
                canciones = obtener_metadatos_ytdlp(url_input, "SoundCloud")
            else:
                canciones = obtener_metadatos_cancion_unica(url_input)

        if not canciones:
            st.error("(Ó╭╮Ò) No se pudieron identificar canciones en la URL proporcionada.")
        else:
            st.success(f"✓ Se identificaron **{len(canciones)}** canciones.")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            descargadas_ok = 0
            omitidas = 0
            fallidas = 0
            archivos_descargados_sesion = []
            
            with st.expander("📋 Ver registro detallado de canciones", expanded=True):
                log_container = st.empty()
                log_lines = []

                for i, item in enumerate(canciones):
                    query_busqueda = item['query_limpia']
                    nombre_archivo = re.sub(r'[\\/*?:"<>|]', "", item['nombre_salida'])
                    ruta_archivo_wav = os.path.join(DOWNLOADS_FOLDER, f'{nombre_archivo}.wav')
                    
                    status_text.text(f"Procesando [{i+1}/{len(canciones)}]: {nombre_archivo[:35]}...")

                    url_objetivo = item.get('url_directa')
                    fuente_nombre = "Enlace Directo"

                    # Si no hay enlace directo, buscar candidatos multifuente
                    if not url_objetivo:
                        candidatos = buscar_candidatos_multifuente(query_busqueda)
                        if not candidatos:
                            omitidas += 1
                            log_lines.append(f"❌ **{query_busqueda}**: Sin fuentes libres encontradas (Omitida)")
                            log_container.markdown("\n\n".join(log_lines))
                            progress_bar.progress((i + 1) / len(canciones))
                            continue

                        # Evaluar similitud con fuzzy matching
                        opciones_evaluadas = []
                        for cand in candidatos[:5]:
                            titulo_cand = cand.get('title', '')
                            uploader = cand.get('uploader') or cand.get('channel') or 'Artista Desconocido'
                            url = cand.get('url') or cand.get('webpage_url')
                            fuente = "SoundCloud" if url and "soundcloud" in url.lower() else "YouTube"
                            score = calcular_similitud(query_busqueda, titulo_cand, uploader)

                            opciones_evaluadas.append({
                                'titulo': titulo_cand,
                                'uploader': uploader,
                                'url': url,
                                'score': score,
                                'fuente': fuente
                            })

                        opciones_evaluadas.sort(key=lambda x: x['score'], reverse=True)
                        mejor_opcion = opciones_evaluadas[0]
                        url_objetivo = mejor_opcion['url']
                        fuente_nombre = f"{mejor_opcion['fuente']} ({mejor_opcion['score']:.0f}% similitud)"

                    # Configuración de descarga con yt-dlp y conversión a WAV directo
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'match_filter': yt_dlp.utils.match_filter_func('duration <= 600'),
                        'extractor_args': {
                            'youtube': {'player_client': ['android', 'ios', 'web']}
                        },
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'wav',
                            'preferredquality': '192',
                        }],
                        'outtmpl': os.path.join(DOWNLOADS_FOLDER, f'{nombre_archivo}.%(ext)s'),
                        'quiet': True,
                        'no_warnings': True,
                        'noprogress': True,
                    }

                    descarga_exitosa = False

                    # Intento 1: URL Principal / Mejor candidato
                    if url_objetivo:
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([url_objetivo])
                            descargadas_ok += 1
                            descarga_exitosa = True
                            archivos_descargados_sesion.append(ruta_archivo_wav)
                            log_lines.append(f"✅ **{nombre_archivo}** → Descargada desde {fuente_nombre}")
                        except Exception:
                            pass

                    # Intento 2: Fallback SoundCloud
                    if not descarga_exitosa:
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([f"scsearch1:{query_busqueda}"])
                            descargadas_ok += 1
                            descarga_exitosa = True
                            archivos_descargados_sesion.append(ruta_archivo_wav)
                            log_lines.append(f"✅ **{nombre_archivo}** → Descargada vía Fallback SoundCloud")
                        except Exception:
                            pass

                    # Intento 3: Fallback YouTube
                    if not descarga_exitosa:
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([f"ytsearch1:{query_busqueda}"])
                            descargadas_ok += 1
                            descarga_exitosa = True
                            archivos_descargados_sesion.append(ruta_archivo_wav)
                            log_lines.append(f"✅ **{nombre_archivo}** → Descargada vía Fallback YouTube")
                        except Exception:
                            fallidas += 1
                            log_lines.append(f"⚠️ **{nombre_archivo}** → Error al descargar en todas las fuentes")

                    log_container.markdown("\n\n".join(log_lines))
                    progress_bar.progress((i + 1) / len(canciones))

            status_text.text("¡Proceso completado!")
            
            st.divider()
            st.markdown("### 📊 RESUMEN FINAL DEL PROCESO")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("♫ Detectadas", len(canciones))
            col2.metric("✦ Descargadas (.WAV)", descargadas_ok)
            col3.metric("シ Omitidas", omitidas)
            col4.metric("♱ Fallidas", fallidas)

            if descargadas_ok > 0 and fallidas == 0 and omitidas == 0:
                st.success("🎉 ¡Proceso 100% completado con éxito!")
            elif descargadas_ok > 0:
                st.info("El proceso finalizó con algunas canciones omitidas o fallidas.")

            if descargadas_ok > 0:
                st.markdown(f"📁 **Canciones guardadas directamente en:** `{DOWNLOADS_FOLDER}`")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("📂 Abrir Carpeta de Descargas", use_container_width=True):
                        try:
                            os.startfile(DOWNLOADS_FOLDER)
                        except Exception:
                            pass
                            
                with col_btn2:
                    zip_buffer = crear_zip_en_memoria(archivos_descargados_sesion)
                    st.download_button(
                        label="📦 Descargar Compilado (.ZIP)",
                        data=zip_buffer,
                        file_name="compilado_dj_ada.zip",
                        mime="application/zip",
                        use_container_width=True,
                        type="primary"
                    )