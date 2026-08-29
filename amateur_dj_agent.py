import os
import re
import html
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import yt_dlp

# -------------------------------------------------------------------
# CONFIGURACIÓN DE RUTAS
# -------------------------------------------------------------------
DOWNLOADS_FOLDER = os.path.expanduser("~/Music/Descargas ADA")
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

# -------------------------------------------------------------------
# MÓDULO 1: EXTRACCIÓN DE METADATOS POR PLATAFORMA
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
                
                # Decodificar caracteres como \u0026 -> &
                titulo = html.unescape(titulo)
                artista = html.unescape(artista)
                
                titulo_lower = titulo.lower()
                artista_lower = artista.lower()
                
                # Filtrar si coincide exactamente con el título o creador de la playlist
                if (titulo_lower == nombre_playlist or 
                    artista_lower == owner_name or 
                    "spotify" in artista_lower or 
                    "user" in artista_lower):
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

        # SOLUCIÓN DE SEGURIDAD: Si el primer elemento sigue siendo la cabecera/título general de la lista,
        # cortamos la lista para que empiece en el índice 1 (canciones[1:])
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
    
    # Limpiar basura de rastreo (?si=..., &utm_source=...)
    url_limpia = url_playlist.split("?")[0].strip()
    
    # Si viene con enlace acortado, resolver redirección
    if "on.soundcloud.com" in url_limpia:
        try:
            res_redir = requests.head(url_limpia, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
            url_limpia = res_redir.url.split("?")[0]
        except Exception:
            pass

    # Para SoundCloud se desactiva extract_flat para forzar la lectura completa de los títulos
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
        
        # Si res no es un listado sino un track individual
        if not entries and res:
            entries = [res]
        
        for entry in entries:
            if not entry:
                continue
            
            titulo = html.unescape(entry.get('title', '').strip())
            uploader = html.unescape((entry.get('uploader') or entry.get('channel') or entry.get('artist') or "Artista Desconocido").strip())
            
            if titulo:
                # Armar la clave de búsqueda limpia
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

# -------------------------------------------------------------------
# MÓDULO 2: ANÁLISIS MULTIFUENTE (YouTube + SoundCloud + Bandcamp)
# -------------------------------------------------------------------
def limpiar_texto(texto):
    return re.sub(r'[^\w\s]', '', texto).strip().lower()

def buscar_candidatos_multifuente(query):
    """
    Busca candidatos en YouTube y SoundCloud descartando automáticamente
    sets o DJ mixes mayores a 10 minutos (600 segundos).
    """
    opts = {
        'quiet': True, 
        'no_warnings': True,
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

    # 1. Búsqueda prioritaria en YouTube
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            res_yt = ydl.extract_info(f"ytsearch3:{query}", download=False)
            if res_yt and res_yt.get('entries'):
                for e in res_yt['entries']:
                    if es_track_valido(e):
                        candidatos.append(e)
        except Exception:
            pass

    # 2. Búsqueda en SoundCloud
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            res_sc = ydl.extract_info(f"scsearch3:{query}", download=False)
            if res_sc and res_sc.get('entries'):
                for e in res_sc['entries']:
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
                'fuente': 'Directa'
            })
            print(f"  ✓ Enlace directo obtenido.\n" + "-" * 65)
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
    print("\n∘₊✧─── FASE 2: Descarga en segundo plano y extracción a .WAV ───✧₊∘\n")
    
    descargadas_ok = 0
    fallidas = 0
    
    for item in lista_verificada:
        nombre_archivo = re.sub(r'[\\/*?:"<>|]', "", item['nombre_salida'])
        
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
        }
        
        print(f"Guardando en 'Descargas ADA': {nombre_archivo}.wav...")
        
        # Intento 1: Fuente seleccionada
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item['url']])
            print(f"  ✓ Descarga completada.\n")
            descargadas_ok += 1
            continue
        except Exception:
            print(f"  ⚠️ Error en fuente ({item.get('fuente', 'Principal')}). Probando Fallback 1: Búsqueda en YouTube...")

        # Intento 2: Fallback 1 -> YouTube
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"ytsearch1:{item['query_original']}"])
            print(f"  ✓ Recuperada con éxito desde YouTube.\n")
            descargadas_ok += 1
            continue
        except Exception:
            print(f"  ⚠️ Fallback YouTube sin éxito. Probando Fallback 2: SoundCloud alternativo...")

        # Intento 3: Fallback 2 -> SoundCloud
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"scsearch1:{item['query_original']}"])
            print(f"  ✓ Recuperada con éxito desde SoundCloud.\n")
            descargadas_ok += 1
        except Exception as e:
            print(f"  ❌ Error final: No se pudo procesar {nombre_archivo} ({e})\n")
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
    print("  [4] Ninguna, salir.\n")
    print("⁺ " * 30)

if __name__ == "__main__":
    while True:
        mostrar_menu()
        opcion = input("Selecciona una opción (1-4): ").strip()
        
        canciones_obtenidas = []
        
        if opcion == "1":
            url_input = input("\n> Ingrese la URL de la Playlist de Spotify: ").strip()
            if url_input:
                canciones_obtenidas = obtener_metadatos_spotify(url_input)
        elif opcion == "2":
            url_input = input("\n> Ingrese la URL de la Playlist de YouTube: ").strip()
            if url_input:
                canciones_obtenidas = obtener_metadatos_ytdlp(url_input, "YouTube")
        elif opcion == "3":
            url_input = input("\n> Ingrese la URL de la Playlist de SoundCloud: ").strip()
            if url_input:
                canciones_obtenidas = obtener_metadatos_ytdlp(url_input, "SoundCloud")
        elif opcion == "4":
            print("\nSaliendo del agente... ¡Buenas sesiones de DJ!")
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
            print("         °˖✧◝(⁰▿⁰)◜✧˖° RESUMEN FINAL DEL PROCESO         ")
            print("⁺ " * 30)
            print(f"\n  ♫ Canciones detectadas en la lista:  {total_detectadas}")
            print(f"  ✦ Descargadas con éxito (.WAV):      {total_exito}")
            print(f"  シ Omitidas (sin fuentes libres):      {total_omitidas}")
            print(f"  ♱ Fallidas (errores de descarga):    {total_fallidas}")
            print("⁺ " * 30)
            
            if total_exito > 0 and total_fallidas == 0:
                print(" (ﾉ>ω<)ﾉ :｡･:*:･ﾟ’★,｡･:*:･ﾟ’☆ ¡Proceso completado al 100%!\n")
                print(" " * 50)
            else:
                print(" (Ó╭╮Ò) El proceso finalizó con algunas advertencias o fallas.\n")