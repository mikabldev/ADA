import html
import io
import os
import re
import zipfile
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from mutagen import File as MutagenFile
from mutagen.id3 import COMM, ID3, TALB, TBPM, TCON, TIT2, TKEY, TPE1, TXXX
from mutagen.wave import WAVE
from rapidfuzz import fuzz
import yt_dlp

DOWNLOADS_FOLDER = os.path.abspath(os.path.expanduser(
    os.getenv("ADA_DOWNLOAD_DIR", "~/Music/Descargas ADA")
))
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)
MAX_WORKERS_DESCARGA = 3
DURACION_TOLERANCIA_SEG = 12

CALIDADES_AUDIO = {
    "WAV 16-bit / 44.1 kHz": {"codec": "pcm_s16le", "sample_rate": "44100"},
    "WAV 24-bit / 48 kHz": {"codec": "pcm_s24le", "sample_rate": "48000"},
}

FUENTES_DISPONIBLES = ("Bandcamp", "SoundCloud", "YouTube")
PRIORIDAD_FUENTES_DEFAULT = FUENTES_DISPONIBLES
TERMINOS_VERSION = {
    "live", "studio", "remix", "mix", "edit", "extended", "remaster",
    "remastered", "instrumental", "acoustic", "cover", "karaoke", "sped up",
    "slowed", "radio edit", "club mix", "demo", "vip",
}
AJUSTES_VERIFICACION_DEFAULT = {
    "modo": "Equilibrado",
    "tolerancia_duracion_seg": DURACION_TOLERANCIA_SEG,
    "similitud_minima": 72,
    "margen_ambiguedad": 8,
    "max_candidatos": 5,
    "revisar_multiples": True,
    "prioridad_fuentes": PRIORIDAD_FUENTES_DEFAULT,
}


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

def limpiar_nombre_archivo(nombre):
    return re.sub(r'[\\/*?:"<>|]', "", nombre).strip()

def dividir_artista_titulo(nombre):
    if " - " in nombre:
        artista, titulo = nombre.split(" - ", 1)
        return artista.strip(), titulo.strip()
    return "Artista Desconocido", nombre.strip()

def obtener_duracion_audio_seg(ruta_audio):
    try:
        audio = MutagenFile(ruta_audio)
        if audio and audio.info and audio.info.length:
            return float(audio.info.length)
    except Exception:
        pass
    return None

def duracion_compatible(ruta_audio, duracion_esperada_ms):
    if not duracion_esperada_ms:
        return True, None
    duracion_real = obtener_duracion_audio_seg(ruta_audio)
    if duracion_real is None:
        return True, None
    esperada_seg = duracion_esperada_ms / 1000
    diferencia = abs(duracion_real - esperada_seg)
    return diferencia <= DURACION_TOLERANCIA_SEG, diferencia

def etiquetar_wav(ruta_audio, item, album="ADA Downloads"):
    artista = item.get('artista') or dividir_artista_titulo(item['nombre_salida'])[0]
    titulo = item.get('titulo') or dividir_artista_titulo(item['nombre_salida'])[1]
    album = item.get('album') or album

    analisis = item.get("analisis_acustico") or {}

    def agregar_etiquetas(tags):
        tags.add(TPE1(encoding=3, text=artista))
        tags.add(TIT2(encoding=3, text=titulo))
        tags.add(TALB(encoding=3, text=album))
        if analisis.get("bpm"):
            tags.add(TBPM(encoding=3, text=f"{analisis['bpm']:.2f}"))
        if analisis.get("camelot"):
            tags.add(TKEY(encoding=3, text=analisis["camelot"]))
            tags.add(TXXX(encoding=3, desc="INITIALKEY", text=analisis["camelot"]))
        if analisis.get("musical_key") and analisis.get("scale"):
            tags.add(TXXX(encoding=3, desc="ADA_MUSICAL_KEY", text=f"{analisis['musical_key']} {analisis['scale']}"))
        genero = item.get("genero") or item.get("genre")
        if genero:
            tags.add(TCON(encoding=3, text=str(genero)))
        for campo, descripcion in (
            ("key_confidence", "ADA_KEY_CONFIDENCE"),
            ("bpm_confidence", "ADA_BPM_CONFIDENCE"),
            ("audible_start_seconds", "ADA_AUDIBLE_START"),
            ("audible_end_seconds", "ADA_AUDIBLE_END"),
            ("fingerprint", "ADA_CHROMAPRINT"),
        ):
            if analisis.get(campo) is not None:
                tags.add(TXXX(encoding=3, desc=descripcion, text=str(analisis[campo])))
        tags.add(COMM(encoding=3, lang="spa", desc="ADA", text="Analizado por ADA"))

    try:
        audio = WAVE(ruta_audio)
        if audio.tags is None:
            audio.add_tags()
        agregar_etiquetas(audio.tags)
        audio.save()
        return True
    except Exception:
        try:
            tags = ID3()
            agregar_etiquetas(tags)
            tags.save(ruta_audio)
            return True
        except Exception:
            return False

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
                api_url = f"https://api.spotify.com/v1/playlists/{playlist_id}?fields=name,owner,tracks.items(track(name,duration_ms,album(name),artists(name)))"
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
                        album = decodificar_texto(track.get('album', {}).get('name', '')) if isinstance(track.get('album'), dict) else ""
                        
                        if not titulo or not artista or titulo.lower() == nombre_playlist:
                            continue
                            
                        clave = f"{artista} - {titulo}"
                        canciones.append({
                            'query_limpia': clave,
                            'nombre_salida': clave,
                            'artista': artista,
                            'titulo': titulo,
                            'album': album,
                            'duration_ms': track.get('duration_ms')
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
                    album = decodificar_texto(track.get('album', {}).get('name', '')) if isinstance(track.get('album'), dict) else ""
                    duration_ms = track.get('duration_ms') or track.get('durationMs')
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
                        'nombre_salida': clave,
                        'artista': artista,
                        'titulo': titulo,
                        'album': album,
                        'duration_ms': duration_ms
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
                    'nombre_salida': clave,
                    'artista': artista_clean,
                    'titulo': titulo_clean,
                    'album': nombre_playlist_meta or "Spotify",
                    'duration_ms': None
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
                    'url_directa': url_cancion if (url_cancion and url_cancion.startswith("http")) else None,
                    'artista': uploader,
                    'titulo': titulo,
                    'album': plataforma,
                    'duration_ms': int(entry['duration'] * 1000) if entry.get('duration') else None
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
            'url_directa': url_limpia,
            'artista': uploader,
            'titulo': titulo,
            'album': "ADA Downloads",
            'duration_ms': int(res['duration'] * 1000) if res.get('duration') else None
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

def buscar_candidatos_bandcamp(query, limite=3):
    """Busca pistas públicas en Bandcamp y obtiene metadatos con yt-dlp."""
    try:
        response = requests.get(
            "https://bandcamp.com/search",
            params={"q": query, "item_type": "t"},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=12,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        urls = []
        for link in soup.select(".searchresult .itemurl a, li.searchresult a.itemurl"):
            url = urljoin(response.url, link.get("href", "")).split("?")[0]
            if url.startswith("http") and url not in urls:
                urls.append(url)
            if len(urls) >= limite:
                break
        candidatos = []
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            for url in urls:
                try:
                    info = ydl.extract_info(url, download=False)
                    if info:
                        info["webpage_url"] = info.get("webpage_url") or url
                        info["_ada_fuente"] = "Bandcamp"
                        candidatos.append(info)
                except Exception:
                    continue
        return candidatos
    except Exception:
        return []


def _buscar_candidatos_fuente(query, fuente):
    if fuente == "Bandcamp":
        return buscar_candidatos_bandcamp(query)
    prefijo = "scsearch3:" if fuente == "SoundCloud" else "ytsearch3:"
    opts = {
        "quiet": True, "no_warnings": True, "ignoreerrors": True,
        "extract_flat": False,
        "match_filter": yt_dlp.utils.match_filter_func("duration <= 600"),
        "extractor_args": {"youtube": {"player_client": ["android", "ios", "web"]}},
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            result = ydl.extract_info(f"{prefijo}{query}", download=False)
        candidatos = []
        for entry in (result or {}).get("entries", []):
            if entry and (not entry.get("duration") or entry["duration"] <= 600):
                entry["_ada_fuente"] = fuente
                candidatos.append(entry)
        return candidatos
    except Exception:
        return []


def buscar_candidatos_multifuente(query, prioridad_fuentes=None):
    """Busca según una prioridad explícita; por defecto Bandcamp, SoundCloud y YouTube."""
    candidatos = []
    for fuente in tuple(prioridad_fuentes or PRIORIDAD_FUENTES_DEFAULT):
        if fuente in FUENTES_DISPONIBLES:
            candidatos.extend(_buscar_candidatos_fuente(query, fuente))
    return candidatos


def _terminos_version(texto):
    normalizado = limpiar_texto(texto)
    return {termino for termino in TERMINOS_VERSION if termino in normalizado}


def evaluar_candidatos(item, candidatos, ajustes=None):
    """Puntúa texto, duración, variante declarada y prioridad de fuente."""
    config = {**AJUSTES_VERIFICACION_DEFAULT, **(ajustes or {})}
    prioridad = tuple(config["prioridad_fuentes"])
    esperada = item.get("duration_ms")
    terminos_solicitud = _terminos_version(item.get("query_limpia", ""))
    evaluados = []
    for candidato in candidatos:
        titulo = candidato.get("title", "")
        uploader = candidato.get("uploader") or candidato.get("channel") or candidato.get("artist") or "Artista desconocido"
        url = candidato.get("webpage_url") or candidato.get("url")
        url_lower = str(url or "").lower()
        fuente = candidato.get("_ada_fuente") or (
            "Bandcamp" if "bandcamp" in url_lower else "SoundCloud" if "soundcloud" in url_lower else "YouTube"
        )
        duracion = candidato.get("duration")
        diferencia = abs(duracion - esperada / 1000) if duracion and esperada else None
        terminos_extra = _terminos_version(f"{titulo} {uploader}") - terminos_solicitud
        score_texto = calcular_similitud(item["query_limpia"], titulo, uploader)
        bonus_fuente = max(0, (len(prioridad) - prioridad.index(fuente)) * 2) if fuente in prioridad else 0
        penalizacion_duracion = min(diferencia * 1.5, 35) if diferencia is not None else 4
        penalizacion_version = 22 * len(terminos_extra)
        score = max(0, min(100, score_texto + bonus_fuente - penalizacion_duracion - penalizacion_version))
        if url:
            evaluados.append({
                "url": url, "titulo": titulo, "uploader": uploader, "fuente": fuente,
                "genero": candidato.get("genre"),
                "duracion_seg": duracion, "diferencia_duracion_seg": diferencia,
                "score_texto": score_texto, "score": score,
                "terminos_version": sorted(terminos_extra),
            })
    evaluados.sort(key=lambda candidato: candidato["score"], reverse=True)
    return evaluados[: int(config["max_candidatos"])]


def clasificar_coincidencia(item, candidatos, ajustes=None):
    """Clasifica una pista como segura, pendiente de revisión o sin coincidencia."""
    config = {**AJUSTES_VERIFICACION_DEFAULT, **(ajustes or {})}
    evaluados = evaluar_candidatos(item, candidatos, config)
    if not evaluados or evaluados[0]["score"] < config["similitud_minima"]:
        return {"estado": "sin_coincidencia", "candidatos": evaluados, "motivos": ["similitud insuficiente"]}
    mejor = evaluados[0]
    motivos = []
    if mejor["terminos_version"]:
        motivos.append("versión alternativa: " + ", ".join(mejor["terminos_version"]))
    if mejor["diferencia_duracion_seg"] is None:
        motivos.append("duración no disponible")
    elif mejor["diferencia_duracion_seg"] > config["tolerancia_duracion_seg"]:
        motivos.append(f"duración difiere {mejor['diferencia_duracion_seg']:.1f}s")
    if len(evaluados) > 1 and mejor["score"] - evaluados[1]["score"] < config["margen_ambiguedad"]:
        motivos.append("candidatos con puntuación similar")
    if config["revisar_multiples"] and len(evaluados) > 1:
        motivos.append("hay varias versiones disponibles")
    requiere_revision = config["modo"] == "Estricto" or (config["modo"] == "Equilibrado" and bool(motivos))
    return {"estado": "revision" if requiere_revision else "segura", "candidatos": evaluados, "motivos": motivos}


def analizar_coincidencia(item, ajustes=None):
    config = {**AJUSTES_VERIFICACION_DEFAULT, **(ajustes or {})}
    if item.get("url_directa"):
        return {"estado": "segura", "candidatos": [{
            "url": item["url_directa"], "titulo": item.get("titulo") or item["nombre_salida"],
            "uploader": item.get("artista") or "Fuente directa", "fuente": "Enlace directo",
            "duracion_seg": item.get("duration_ms", 0) / 1000 if item.get("duration_ms") else None,
            "genero": item.get("genero") or item.get("genre"),
            "diferencia_duracion_seg": 0, "score_texto": 100, "score": 100,
            "terminos_version": [],
        }], "motivos": []}
    candidatos = buscar_candidatos_multifuente(item["query_limpia"], config["prioridad_fuentes"])
    return clasificar_coincidencia(item, candidatos, config)

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


def crear_zip_en_disco(rutas_archivos, ruta_zip):
    """Crea un ZIP en disco usando únicamente nombres base seguros."""
    os.makedirs(os.path.dirname(os.path.abspath(ruta_zip)), exist_ok=True)
    with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for ruta in rutas_archivos:
            if os.path.isfile(ruta):
                zipf.write(ruta, arcname=os.path.basename(ruta))
    return ruta_zip

def construir_ydl_opts(nombre_archivo, calidad_audio, directorio_salida=None, progress_hooks=None):
    calidad = CALIDADES_AUDIO[calidad_audio]
    directorio_salida = os.path.abspath(directorio_salida or DOWNLOADS_FOLDER)
    os.makedirs(directorio_salida, exist_ok=True)
    return {
        'format': 'bestaudio/best',
        'match_filter': yt_dlp.utils.match_filter_func('duration <= 600'),
        'extractor_args': {
            'youtube': {'player_client': ['android', 'ios', 'web']}
        },
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
        'postprocessor_args': ['-ar', calidad['sample_rate'], '-acodec', calidad['codec']],
        'outtmpl': os.path.join(directorio_salida, f'{nombre_archivo}.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'progress_hooks': progress_hooks or [],
    }

def resolver_url_objetivo(item, ajustes=None):
    query_busqueda = item['query_limpia']
    url_objetivo = item.get('url_directa')
    fuente_nombre = "Enlace Directo"

    if url_objetivo:
        return url_objetivo, fuente_nombre, None

    analisis = analizar_coincidencia(item, ajustes)
    if not analisis["candidatos"]:
        return None, None, "Sin fuentes libres encontradas"
    if analisis["estado"] == "revision":
        return None, None, "Requiere revisión humana antes de descargar"
    mejor_opcion = analisis["candidatos"][0]
    return mejor_opcion['url'], f"{mejor_opcion['fuente']} ({mejor_opcion['score']:.0f}% similitud)", None

def descargar_item(item, calidad_audio, directorio_salida=None, progress_hooks=None):
    directorio_salida = os.path.abspath(directorio_salida or DOWNLOADS_FOLDER)
    os.makedirs(directorio_salida, exist_ok=True)
    nombre_archivo = limpiar_nombre_archivo(item['nombre_salida'])
    ruta_archivo_wav = os.path.join(directorio_salida, f'{nombre_archivo}.wav')

    if os.path.exists(ruta_archivo_wav):
        ok_duracion, diferencia = duracion_compatible(ruta_archivo_wav, item.get('duration_ms'))
        if ok_duracion:
            analisis = None
            try:
                from ada_audio import analyze_audio
                analisis = analyze_audio(ruta_archivo_wav).to_dict()
                item = {**item, "analisis_acustico": analisis}
            except Exception:
                pass
            etiquetar_wav(ruta_archivo_wav, item)
            return {
                'estado': 'omitida_existente',
                'nombre': nombre_archivo,
                'ruta': ruta_archivo_wav,
                'mensaje': f"**{nombre_archivo}** ya existía y fue omitida",
                'analisis_acustico': analisis,
            }
        return {
            'estado': 'fallida',
            'nombre': nombre_archivo,
            'ruta': ruta_archivo_wav,
            'mensaje': f"**{nombre_archivo}** ya existía, pero la duración difiere por {diferencia:.1f}s"
        }

    url_objetivo, fuente_nombre, error = resolver_url_objetivo(item)
    if error:
        return {
            'estado': 'omitida',
            'nombre': nombre_archivo,
            'ruta': None,
            'mensaje': f"**{item['query_limpia']}**: {error}"
        }

    ydl_opts = construir_ydl_opts(nombre_archivo, calidad_audio, directorio_salida, progress_hooks)
    intentos = [(url_objetivo, item.get("fuente_seleccionada") or fuente_nombre)]
    if not item.get("bloquear_fallback"):
        intentos.extend([
            (f"scsearch1:{item['query_limpia']}", "Fallback SoundCloud"),
            (f"ytsearch1:{item['query_limpia']}", "Fallback YouTube"),
        ])

    for url_descarga, fuente in intentos:
        if not url_descarga:
            continue
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url_descarga])
            if not os.path.exists(ruta_archivo_wav):
                continue
            ok_duracion, diferencia = duracion_compatible(ruta_archivo_wav, item.get('duration_ms'))
            if not ok_duracion:
                return {
                    'estado': 'fallida',
                    'nombre': nombre_archivo,
                    'ruta': ruta_archivo_wav,
                    'mensaje': f"**{nombre_archivo}** descargada desde {fuente}, pero la duración difiere por {diferencia:.1f}s"
                }
            analisis = None
            try:
                from ada_audio import analyze_audio
                analisis = analyze_audio(ruta_archivo_wav).to_dict()
                item = {**item, "analisis_acustico": analisis}
            except Exception:
                pass
            etiquetas_ok = etiquetar_wav(ruta_archivo_wav, item)
            nota_tags = "" if etiquetas_ok else " (sin etiquetas ID3)"
            return {
                'estado': 'descargada',
                'nombre': nombre_archivo,
                'ruta': ruta_archivo_wav,
                'mensaje': f"**{nombre_archivo}** descargada desde {fuente}{nota_tags}",
                'analisis_acustico': analisis,
            }
        except Exception:
            continue

    return {
        'estado': 'fallida',
        'nombre': nombre_archivo,
        'ruta': None,
        'mensaje': f"**{nombre_archivo}**: error al descargar en todas las fuentes"
    }
