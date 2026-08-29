import os
import re
from dotenv import load_dotenv  # <--- Librería para cargar el archivo .env
from rapidfuzz import fuzz
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp

# -------------------------------------------------------------------
# CARGA DE CREDENCIALES DESDE VARIABLES DE ENTORNO (.env)
# -------------------------------------------------------------------
load_dotenv()  # Lee las variables del archivo .env local

SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')

# Validar que las credenciales estén cargadas antes de continuar
if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET:
    raise ValueError("❌ No se encontraron las credenciales de Spotify. Revisa el archivo .env.")

# Carpeta de destino personalizada (Mi Música / Descargas ADA)
DOWNLOADS_FOLDER = os.path.expanduser("~/Music/Descargas ADA")
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

# Autenticación con Spotify
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET
))

# -------------------------------------------------------------------
# MÓDULO 1: OBTENCIÓN DE DATOS DESDE SPOTIFY
# -------------------------------------------------------------------
def obtener_canciones_de_playlist(playlist_url_o_id):
    """
    Lee una playlist de Spotify procesando la URL o ID.
    """
    print("=== Extrayendo metadatos de la Playlist de Spotify ===")
    lista_canciones = []
    
    # Limpiar la URL para extraer únicamente el ID de la playlist
    if "spotify.com/playlist/" in playlist_url_o_id:
        # Extrae el ID eliminando parámetros extra como ?si=...
        playlist_id = playlist_url_o_id.split("playlist/")[1].split("?")[0]
    else:
        playlist_id = playlist_url_o_id
        
    try:
        resultados = sp.playlist_items(playlist_id)
        tracks = resultados['items']
        
        # Paginación para playlists largas (> 100 temas)
        while resultados['next']:
            resultados = sp.next(resultados)
            tracks.extend(resultados['items'])
            
        for item in tracks:
            track = item.get('track')
            if not track or not track.get('name'):
                continue
                
            titulo = track['name']
            artista = track['artists'][0]['name']
            lista_canciones.append({
                'query_limpia': f"{artista} - {titulo}",
                'nombre_salida': f"{artista} - {titulo}"
            })
            
        print(f"  ✓ Se obtuvieron {len(lista_canciones)} canciones de la playlist.\n")
        return lista_canciones
        
    except Exception as e:
        print(f"❌ Error al conectar con Spotify: {e}")
        return []

def limpiar_texto(texto):
    """Limpia cadenas para comparaciones de similitud."""
    return re.sub(r'[^\w\s]', '', texto).strip().lower()

# -------------------------------------------------------------------
# MÓDULO 2: ANÁLISIS DE SIMILITUD Y SELECCIÓN DE FUENTES
# -------------------------------------------------------------------
def analizar_y_resolver_coincidencias(lista_canciones):
    """
    Busca opciones en fuentes públicas mediante yt-dlp y compara
    la similitud del título antes de autorizar la descarga.
    """
    canciones_procesadas = []
    
    print("=== FASE 1: Análisis y verificación de coincidencias ===\n")
    
    for i, item in enumerate(lista_canciones):
        query_busqueda = item['query_limpia']
        print(f"Procesando [{i+1}/{len(lista_canciones)}]: '{query_busqueda}'")
            
        # Buscar candidato de audio
        opts = {'quiet': True, 'default_search': 'ytsearch3:', 'extract_flat': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            res = ydl.extract_info(query_busqueda, download=False)
            
        candidatos = res.get('entries', []) if res else []
        
        if not candidatos:
            print(f"  ❌ No se encontraron fuentes para '{query_busqueda}'. Omitiendo.\n")
            continue
            
        opciones_evaluadas = []
        for cand in candidatos[:3]:
            titulo_cand = cand.get('title', '')
            uploader = cand.get('uploader', 'Artista Desconocido')
            url = cand.get('url') or cand.get('webpage_url')
            
            score = fuzz.WRatio(limpiar_texto(query_busqueda), limpiar_texto(titulo_cand))
            
            opciones_evaluadas.append({
                'titulo_audio': titulo_cand,
                'uploader': uploader,
                'url': url,
                'score': score,
                'nombre_salida': item['nombre_salida']
            })
            
        opciones_evaluadas.sort(key=lambda x: x['score'], reverse=True)
        
        # Alerta interactiva si hay incertidumbre (< 85% de similitud)
        if len(opciones_evaluadas) > 1 and opciones_evaluadas[0]['score'] < 85:
            print(f"  ⚠️ Alerta de Similitud: Diferencia detectada entre metadatos y fuente.")
            print("     Selecciona la opción correcta:")
            
            for idx, opc in enumerate(opciones_evaluadas, start=1):
                print(f"     [{idx}] {opc['titulo_audio']} | Canal: {opc['uploader']} ({opc['score']:.1f}%)")
                
            while True:
                try:
                    eleccion = int(input("     Selecciona una opción (1-3): "))
                    if 1 <= eleccion <= len(opciones_evaluadas):
                        seleccionada = opciones_evaluadas[eleccion - 1]
                        break
                except ValueError:
                    pass
                print("     Opción no válida.")
        else:
            seleccionada = opciones_evaluadas[0]
            print(f"  ✓ Coincidencia validada: '{seleccionada['titulo_audio']}' ({seleccionada['score']:.1f}%)")
            
        canciones_procesadas.append(seleccionada)
        print("-" * 65)
        
    return canciones_procesadas

# -------------------------------------------------------------------
# MÓDULO 3: DESCARGA Y CONVERSIÓN A WAV
# -------------------------------------------------------------------
def descargar_canciones(lista_verificada):
    """
    Descarga el audio en segundo plano a la carpeta especificada y convierte a .wav.
    """
    print("\n=== FASE 2: Descarga en segundo plano y extracción a .WAV ===\n")
    
    for item in lista_verificada:
        nombre_archivo = re.sub(r'[\\/*?:"<>|]', "", item['nombre_salida'])
        
        ydl_opts = {
            'format': 'bestaudio/best',
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
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item['url']])
            print(f"  ✓ Descarga completada.\n")
        except Exception as e:
            print(f"  ❌ Error al procesar {nombre_archivo}: {e}\n")

# -------------------------------------------------------------------
# EJECUCIÓN PRINCIPAL
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Pega aquí la URL de tu playlist de Spotify
    URL_PLAYLIST = "https://open.spotify.com/playlist/TU_PLAYLIST_ID_AQUI"
    
    print("Iniciando Agente de Procesamiento de Música...\n")
    
    # 1. Obtener lista desde Spotify
    canciones_playlist = obtener_canciones_de_playlist(URL_PLAYLIST)
    
    # 2. Verificar coincidencias y descargar
    if canciones_playlist:
        canciones_listas = analizar_y_resolver_coincidencias(canciones_playlist)
        if canciones_listas:
            descargar_canciones(canciones_listas)
            print("🎉 ¡Todas las canciones han sido procesadas y guardadas en .wav!")