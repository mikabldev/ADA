import os
import re
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
    Extrae los metadatos de una playlist pública de Spotify sin API Keys.
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
            tracks = data.get('tracks', {}).get('items', [])
            
            for item in tracks:
                track = item.get('track', item)
                titulo = track.get('name', '').strip()
                artistas = track.get('artists', [])
                artista = artistas[0].get('name', '').strip() if artistas else ""
                
                if not titulo or not artista:
                    continue
                
                if titulo.lower() == nombre_playlist or "spotify" in artista.lower():
                    continue
                    
                clave = f"{artista} - {titulo}"
                canciones.append({
                    'query_limpia': clave,
                    'nombre_salida': clave
                })
        else:
            matches = re.findall(r'"title":"([^"]+)".*?"subtitle":"([^"]+)"', response.text)
            for titulo, artista in matches:
                if "spotify" in artista.lower():
                    continue
                clave = f"{artista} - {titulo}"
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
    Extrae los metadatos de playlists públicas o no listadas de YouTube o SoundCloud.
    """
    print(f"\n∘₊✧─── Leyendo metadatos desde {plataforma} ───✧₊∘")
    canciones = []
    
    opts = {
        'extract_flat': True,
        'quiet': True,
        'skip_download': True
    }
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            res = ydl.extract_info(url_playlist, download=False)
            
        entries = res.get('entries', []) if res else []
        
        for entry in entries:
            if not entry:
                continue
            
            titulo = entry.get('title', '').strip()
            uploader = (entry.get('uploader') or entry.get('channel') or "Artista Desconocido").strip()
            
            if titulo:
                clave = titulo if " - " in titulo else f"{uploader} - {titulo}"
                canciones.append({
                    'query_limpia': clave,
                    'nombre_salida': clave,
                    'url_directa': entry.get('url') or entry.get('webpage_url')
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

    # 1. Búsqueda prioritaria en YouTube (evita DRM de SoundCloud)
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
            
            # Identificación explícita de plataforma
            if "bandcamp" in url.lower():
                fuente = "Bandcamp"
            elif "soundcloud" in url.lower():
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
# MÓDULO 3: DESCARGA CON SISTEMA DE FALLBACK TRIPLE (SIN MUTAGEN)
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

        # Intento 2: Fallback 1 -> YouTube (Resuelve bloqueos DRM de SoundCloud)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"ytsearch1:{item['query_original']}"])
            print(f"  ✓ Recuperada con éxito desde YouTube.\n")
            descargadas_ok += 1
            continue
        except Exception:
            print(f"  ⚠️ Fallback YouTube sin éxito. Probando Fallback 2: SoundCloud alternativo...")

        # Intento 3: Fallback 2 -> SoundCloud alternativo
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
            print("⁺ " * 60)
            print("         °˖✧◝(⁰▿⁰)◜✧˖° RESUMEN FINAL DEL PROCESO         ")
            print("⁺ " * 60)
            print(f"\n  ♫ Canciones detectadas en la lista:  {total_detectadas}")
            print(f"  ✦ Descargadas con éxito (.WAV):      {total_exito}")
            print(f"  シ Omitidas (sin fuentes libres):      {total_omitidas}")
            print(f"  ♱ Fallidas (errores de descarga):    {total_fallidas}")
            print("⁺ " * 60)
            
            if total_exito > 0 and total_fallidas == 0:
                print(" (ﾉ>ω<)ﾉ :｡･:*:･ﾟ’★,｡･:*:･ﾟ’☆ ¡Proceso completado al 100%!\n")
            else:
                print(" (Ó╭╮Ò) El proceso finalizó con algunas advertencias o fallas.\n")