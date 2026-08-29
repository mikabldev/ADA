import os
import re
import html
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import yt_dlp
from tqdm import tqdm

# -------------------------------------------------------------------
# CONFIGURACIÓN DE RUTAS
# -------------------------------------------------------------------
DOWNLOADS_FOLDER = os.path.expanduser("~/Music/Descargas ADA")
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

# -------------------------------------------------------------------
# MÓDULO 1: EXTRACCIÓN DE METADATOS (PLAYLISTS Y CANCIÓN INDIVIDUAL)
# -------------------------------------------------------------------

def obtener_metadatos_spotify(url_playlist):
    """
    Extrae los metadatos de una playlist pública de Spotify decodificando caracteres Unicode
    y filtrando la cabecera de la lista.
    """
    print("\n∘₊✧─── Leyendo metadatos desde Spotify ───✧₊∘")
    
    if "playlist/" in url_playlist:
        playlist_id = url_playlist.strip().split("playlist/")[1].split("?")[0]
    else:
        playlist_id = url_playlist.strip().split("?")[0]
    
    embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(embed_url, headers=headers)
        if response.status_code != 200:
            print(f"(ᗒᗣᗕ)՞ No fue posible acceder a la playlist de Spotify (HTTP {response.status_code})")
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
            
            tracks = data.get('tracks', {}).get('items', [])
            
            for item in tracks:
                track = item.get('track', item)
                titulo = track.get('name', '').strip()
                artistas = track.get('artists', [])
                artista = artistas[0].get('name', '').strip() if artistas else ""
                
                if not titulo or not artista:
                    continue
                
                titulo = html.unescape(titulo)
                artista = html.unescape(artista)
                
                if (titulo.lower() == nombre_playlist or 
                    artista.lower() == owner_name or 
                    "spotify" in artista.lower() or 
                    "user" in artista.lower()):
                    continue
                    
                clave = f"{artista} - {titulo}"
                canciones.append({
                    'query_limpia': clave,
                    'nombre_salida': clave
                })
        else:
            matches = re.findall(r'"title":"([^"]+)".*?"subtitle":"([^"]+)"', response.text)
            for titulo, artista in matches:
                titulo_clean = html.unescape(titulo)
                artista_clean = html.unescape(artista)
                if "spotify" in artista_clean.lower():
                    continue
                clave = f"{artista_clean} - {titulo_clean}"
                canciones.append({
                    'query_limpia': clave,
                    'nombre_salida': clave
                })

        if canciones and ("spotify" in canciones[0]['query_limpia'].lower() or "user" in canciones[0]['query_limpia'].lower()):
            canciones = canciones[1:]

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
        'skip_download': True
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

    opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            res = ydl.extract_info(url_limpia, download=False)
            
        if not res:
            print("❌ No se pudo extraer información del enlace.")
            return []
            
        titulo = html.unescape(res.get('title', '').strip())
        uploader = html.unescape((res.get('uploader') or res.get('channel') or res.get('artist') or "Artista Desconocido").strip())
        
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
# MÓDULO 2: ANÁLISIS MULTIFUENTE (YouTube + SoundCloud)
# -------------------------------------------------------------------
def limpiar_texto(texto):
    return re.sub(r'[^\w\s]', '', texto).strip().lower()

def buscar_candidatos_multifuente(query):
    """
    Busca candidatos dando prioridad a SoundCloud y silenciando warnings.
    """
    opts = {
        'quiet': True, 
        'no_warnings': True,
        'ignoreerrors': True,
        'extract_flat': False,
        'match_filter': yt_dlp.utils.match_filter_func('duration <= 600')
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
            
            if "soundcloud" in url.lower():
                fuente = "SoundCloud"
            else:
                fuente = "YouTube"
            
            score = fuzz.WRatio(limpiar_texto(query_busqueda), limpiar_texto(titulo_cand))
            
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
# MÓDULO 3: DESCARGA CON SISTEMA DE FALLBACK TRIPLE
# -------------------------------------------------------------------
def descargar_canciones(lista_verificada):
    print("\n∘₊✧─── FASE 2: Descarga y conversión a .WAV ───✧₊∘\n")
    
    descargadas_ok = 0
    fallidas = 0
    
    # tqdm genera la barra única [██████████████████] 100%
    barra_progreso = tqdm(
        lista_verificada, 
        desc="Descargando canciones", 
        unit="track", 
        bar_format="{l_bar}{bar:30}{r_bar}"
    )
    
    for item in barra_progreso:
        nombre_archivo = re.sub(r'[\\/*?:"<>|]', "", item['nombre_salida'])
        
        # Actualiza el texto visible al lado de la barra con la canción actual
        barra_progreso.set_postfix_str(f"Procesando: {nombre_archivo[:25]}...")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'match_filter': yt_dlp.utils.match_filter_func('duration <= 600'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(DOWNLOADS_FOLDER, f'{nombre_archivo}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noprogress': True, # Silencia el log ruidoso de la captura
        }
        
        # Intento 1: URL Principal
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item['url']])
            descargadas_ok += 1
            continue
        except Exception:
            pass

        # Intento 2: Fallback SoundCloud
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"scsearch1:{item['query_original']}"])
            descargadas_ok += 1
            continue
        except Exception:
            pass

        # Intento 3: Fallback YouTube
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"ytsearch1:{item['query_original']}"])
            descargadas_ok += 1
        except Exception:
            fallidas += 1
                
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