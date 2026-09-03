import os
import re
import html
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import yt_dlp
from tqdm import tqdm

import sys

# Asegurar codificación UTF-8 en consola de Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# -------------------------------------------------------------------
# CONFIGURACIÓN DE RUTAS Y UTILIDADES DE TEXTO
# -------------------------------------------------------------------
DOWNLOADS_FOLDER = os.path.expanduser("~/Music/Descargas ADA")
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

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

# -------------------------------------------------------------------
# MÓDULO 1: EXTRACCIÓN DE METADATOS (PLAYLISTS Y CANCIÓN INDIVIDUAL)
# -------------------------------------------------------------------

def obtener_metadatos_spotify(url_playlist):
    """
    Extrae los metadatos de una playlist pública de Spotify decodificando caracteres Unicode
    y filtrando estrictamente la cabecera de la lista.
    Utiliza la API web de Spotify con token anónimo oficial y fallback a embed HTML con cabeceras completas.
    """
    print("\n∘₊✧─── Leyendo metadatos desde Spotify ───✧₊∘")
    
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

    # 1. INTENTO 1: API Oficial de Spotify con Token Web Anónimo (Evita HTTP 403 de raíz)
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
                        print(f"  ✓ Se identificaron {len(canciones)} canciones en Spotify (vía Web API directa).\n")
                        return canciones
    except Exception:
        pass

    # 2. INTENTO 2: Embed HTML con cabeceras completas de navegador
    embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
    try:
        response = requests.get(embed_url, headers=headers_browser, timeout=10)
        if response.status_code != 200:
            print(f"(ᗒᗣᗕ)՞ No fue posible acceder a la playlist de Spotify (HTTP {response.status_code})")
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

        print(f"  ✓ Se identificaron {len(canciones)} canciones en Spotify.\n")
        return canciones

    except Exception as e:
        print(f"❌ Error al leer los datos de Spotify: {e}\n")
        return []

def obtener_metadatos_ytdlp(url_playlist, plataforma="YouTube / SoundCloud"):
    """
    Extrae los metadatos de playlists de SoundCloud/YouTube soportando
    sets públicos de SoundCloud, URLs acortadas y parámetros de rastreo.
    """
    print(f"\n∘₊✧─── Leyendo metadatos desde {plataforma} ───✧₊∘")
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
                
        print(f"  ✓ Se identificaron {len(canciones)} canciones en {plataforma}.\n")
        return canciones
        
    except Exception as e:
        print(f"❌ Error al procesar la playlist de {plataforma}: {e}\n")
        return []

def obtener_metadatos_cancion_unica(url_cancion):
    """
    Extrae los metadatos de 1 sola canción desde SoundCloud, YouTube o Bandcamp.
    """
    print("\n∘₊✧─── Obteniendo metadatos del enlace individual ───✧₊∘")
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
            print("❌ No se pudo extraer información del enlace.")
            return []
            
        titulo = decodificar_texto(res.get('title', '').strip())
        uploader = decodificar_texto((res.get('uploader') or res.get('channel') or res.get('artist') or "Artista Desconocido").strip())
        
        clave = titulo if " - " in titulo else f"{uploader} - {titulo}"
        
        print(f"  ✓ Canción identificada: '{clave}'\n")
        return [{
            'query_limpia': clave,
            'nombre_salida': clave,
            'url_directa': url_limpia
        }]
        
    except Exception as e:
        print(f"❌ Error al procesar el enlace individual: {e}\n")
        return []

# -------------------------------------------------------------------
# MÓDULO 2: ANÁLISIS MULTIFUENTE Y FILTRADO DE SIMILITUD
# -------------------------------------------------------------------
def limpiar_texto(texto):
    t = re.sub(r'[^\w\s]', ' ', texto)
    return ' '.join(t.split()).lower()

def calcular_similitud(query, titulo_cand, uploader=""):
    """
    Calcula el índice de similitud real basado en los metadatos de origen,
    tolerando diferencias en el orden de artistas, etiquetas adicionales
    y separación entre canal y título.
    """
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

def analizar_y_resolver_coincidencias(lista_canciones):
    canciones_procesadas = []
    omitidas = 0
    print("∘₊✧─── FASE 1: Análisis y verificación de coincidencias ───✧₊∘\n")
    
    for i, item in enumerate(lista_canciones):
        query_busqueda = item['query_limpia']
        print(f"Procesando [{i+1}/{len(lista_canciones)}]: '{query_busqueda}'")
            
        if item.get('url_directa'):
            canciones_procesadas.append({
                'url': item['url_directa'],
                'nombre_salida': item['nombre_salida'],
                'query_original': query_busqueda,
                'fuente': 'Enlace Directo'
            })
            print(f"  ✓ Enlace directo validado.\n" + "-" * 65)
            continue

        candidatos = buscar_candidatos_multifuente(query_busqueda)
        
        if not candidatos:
            print(f"  🕱︎ No se encontraron fuentes públicas para '{query_busqueda}'. Omitiendo.\n")
            omitidas += 1
            continue
            
        opciones_evaluadas = []
        for cand in candidatos[:5]:
            titulo_cand = cand.get('title', '')
            uploader = cand.get('uploader') or cand.get('channel') or 'Artista Desconocido'
            url = cand.get('url') or cand.get('webpage_url')
            
            if url and "soundcloud" in url.lower():
                fuente = "SoundCloud"
            else:
                fuente = "YouTube"
            
            score = calcular_similitud(query_busqueda, titulo_cand, uploader)
            
            opciones_evaluadas.append({
                'titulo_audio': titulo_cand,
                'uploader': uploader,
                'url': url,
                'score': score,
                'fuente': fuente,
                'nombre_salida': item['nombre_salida'],
                'query_original': query_busqueda
            })
            
        opciones_evaluadas.sort(key=lambda x: x['score'], reverse=True)
        
        if len(opciones_evaluadas) > 1 and opciones_evaluadas[0]['score'] < 85:
            print(f"  (⇀‸↼‶) ¡Alerta de Similitud! 🡪 Diferencia detectada entre metadatos y fuente.")
            print("     Selecciona la opción correcta:")
            
            for idx, opc in enumerate(opciones_evaluadas, start=1):
                print(f"     [{idx}] [{opc['fuente']}] {opc['titulo_audio']} | Canal: {opc['uploader']} ({opc['score']:.1f}%)")
                
            while True:
                try:
                    eleccion = int(input(f"     Selecciona una opción (1-{len(opciones_evaluadas)}): "))
                    if 1 <= eleccion <= len(opciones_evaluadas):
                        seleccionada = opciones_evaluadas[eleccion - 1]
                        break
                except ValueError:
                    pass
                print("     Opción no válida.")
        else:
            seleccionada = opciones_evaluadas[0]
            print(f"  ♡⃕ Coincidencia validada en [{seleccionada['fuente']}]: '{seleccionada['titulo_audio']}' ({seleccionada['score']:.1f}%)")
            
        canciones_procesadas.append(seleccionada)
        print("-" * 65)
        
    return canciones_procesadas, omitidas

# -------------------------------------------------------------------
# MÓDULO 3: DESCARGA CON SISTEMA DE FALLBACK TRIPLE Y BARRA CONTINUA
# -------------------------------------------------------------------
def descargar_canciones(lista_verificada):
    print("\n∘₊✧─── FASE 2: Descarga y conversión a .WAV ───✧₊∘\n")
    
    descargadas_ok = 0
    fallidas = 0
    total_tracks = len(lista_verificada)
    
    for i, item in enumerate(lista_verificada, start=1):
        nombre_archivo = re.sub(r'[\\/*?:"<>|]', "", item['nombre_salida'])
        print(f"[{i}/{total_tracks}] 🎵 Descargando: '{nombre_archivo}'")
        
        # Barra de progreso interactiva por pista para ver el llenado continuo
        pbar = tqdm(
            total=100, 
            desc="   ↳ Descarga", 
            unit="%", 
            bar_format="{desc}: [{bar:30}] {percentage:3.0f}% | {postfix}",
            leave=False,
            dynamic_ncols=True
        )
        pbar.set_postfix_str("Conectando...")
        
        def ytdl_hook(d):
            if d.get('status') == 'downloading':
                total_b = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded_b = d.get('downloaded_bytes', 0)
                if total_b and total_b > 0:
                    pct = int((downloaded_b / total_b) * 100)
                    pbar.n = min(pct, 99)
                    vel = d.get('_speed_str', '')
                    pbar.set_postfix_str(f"Descargando {vel}")
                    pbar.refresh()
            elif d.get('status') == 'finished':
                pbar.n = 100
                pbar.set_postfix_str("Convirtiendo a WAV...")
                pbar.refresh()

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
            'progress_hooks': [ytdl_hook]
        }
        
        descargada = False
        
        # Intento 1: URL Principal
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item['url']])
            descargada = True
        except Exception:
            pass

        # Intento 2: Fallback SoundCloud
        if not descargada:
            pbar.set_postfix_str("Fallback SoundCloud...")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"scsearch1:{item['query_original']}"])
                descargada = True
            except Exception:
                pass

        # Intento 3: Fallback YouTube
        if not descargada:
            pbar.set_postfix_str("Fallback YouTube...")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"ytsearch1:{item['query_original']}"])
                descargada = True
            except Exception:
                pass
                
        pbar.close()
        
        if descargada:
            descargadas_ok += 1
            print(f"   ✓ Audio listo: '{nombre_archivo}.wav'\n" + "-" * 65)
        else:
            fallidas += 1
            print(f"   ❌ Falló la descarga: '{nombre_archivo}'\n" + "-" * 65)
                
    return descargadas_ok, fallidas

# -------------------------------------------------------------------
# MENÚ INTERACTIVO PRINCIPAL
# -------------------------------------------------------------------
def mostrar_menu():
    print("⁺ " * 30)
    print("      WELCOME TO AMATEUR DJ AGENT (ADA) - MUSIC DOWNLOADER")
    print("⁺ " * 30)
    print("\n ¿Desde dónde descargarás? Nuestras opciones son:")
    print("  [1] Playlist de Spotify (URL pública)")
    print("  [2] Playlist de YouTube (URL pública / no listada)")
    print("  [3] Playlist de SoundCloud (URL pública / no listada)")
    print("  [4] Una sola canción (URL de SoundCloud, YouTube o Bandcamp)")
    print("  [5] Ninguna, salir.\n")
    print("⁺ " * 30)

if __name__ == "__main__":
    while True:
        mostrar_menu()
        opcion = input("Selecciona una opción (1-5): ").strip()
        
        canciones_obtenidas = []
        
        if opcion == "1":
            url_input = input("\n> Ingresa la URL de la Playlist de Spotify: ").strip()
            if url_input:
                canciones_obtenidas = obtener_metadatos_spotify(url_input)
        elif opcion == "2":
            url_input = input("\n> Ingresa la URL de la Playlist de YouTube: ").strip()
            if url_input:
                canciones_obtenidas = obtener_metadatos_ytdlp(url_input, "YouTube")
        elif opcion == "3":
            url_input = input("\n> Ingresa la URL de la Playlist de SoundCloud: ").strip()
            if url_input:
                canciones_obtenidas = obtener_metadatos_ytdlp(url_input, "SoundCloud")
        elif opcion == "4":
            url_input = input("\n> Ingresa la URL de la canción (SoundCloud / YouTube / Bandcamp): ").strip()
            if url_input:
                canciones_obtenidas = obtener_metadatos_cancion_unica(url_input)
        elif opcion == "5":
            print("\nSaliendo del agente... ¡Buenas mezclas, DJ!")
            break
        else:
            print("Esa opción no es válida. Intenta nuevamente.\n")
            continue

        if canciones_obtenidas:
            total_detectadas = len(canciones_obtenidas)
            canciones_verificadas, total_omitidas = analizar_y_resolver_coincidencias(canciones_obtenidas)
            
            total_exito = 0
            total_fallidas = 0
            
            if canciones_verificadas:
                total_exito, total_fallidas = descargar_canciones(canciones_verificadas)
            
            # Resumen real de métricas
            print("⁺ " * 30)
            print("        °˖✧◝(⁰▿⁰)◜✧˖°   RESUMEN FINAL DEL PROCESO  °˖✧◝(⁰▿⁰)◜✧˖°")
            print("⁺ " * 30)
            print(f"\n  ♫ Canciones detectadas:              {total_detectadas}")
            print(f"  ✦ Descargadas con éxito (.WAV):      {total_exito}")
            print(f"  シ Omitidas (sin fuentes libres):      {total_omitidas}")
            print(f"  ♱ Fallidas (errores de descarga):    {total_fallidas}")
            print("⁺ " * 30)
            
            if total_exito > 0 and total_fallidas == 0:
                print(" ⊱ ────── {.⋅ ♫  𝑷𝑹𝑶𝑪𝑬𝑺𝑶 𝟏𝟎𝟎% 𝑪𝑶𝑴𝑷𝑳𝑬𝑻𝑨𝑫𝑶 (ﾉ>ω<)ﾉ  ♫ ⋅.} ───── ⊰ \n")
            else:
                print(" (Ó╭╮Ò) El proceso finalizó con algunas advertencias o fallas.\n")
                # (ﾉ>ω<)ﾉ 