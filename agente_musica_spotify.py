import os
import re
from dotenv import load_dotenv
from rapidfuzz import fuzz
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp

# -------------------------------------------------------------------
# CARGA DE CREDENCIALES Y CONFIGURACIÓN
# -------------------------------------------------------------------
load_dotenv()

SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')

if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET:
    raise ValueError("❌ No se encontraron las credenciales de Spotify en el archivo .env")

# Ruta de destino personalizada (Mi Música / Descargas ADA)
DOWNLOADS_FOLDER = os.path.expanduser("~/Music/Descargas ADA")
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

# Cliente de Spotify
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET
))

# -------------------------------------------------------------------
# MÓDULOS DE PROCESAMIENTO
# -------------------------------------------------------------------
def extraer_playlist_id(entrada_usuario):
    """
    Limpia la entrada del usuario para extraer únicamente el ID de la playlist
    incluso si incluye sufijos como '?si=...' o enlaces completos.
    """
    entrada = entrada_usuario.strip()
    if "spotify.com/playlist/" in entrada:
        return entrada.split("playlist/")[1].split("?")[0]
    return entrada.split("?")[0]

def obtener_canciones_de_playlist(playlist_input):
    playlist_id = extraer_playlist_id(playlist_input)
    print("\n=== Extrayendo metadatos de la Playlist de Spotify ===")
    lista_canciones = []
    
    try:
        resultados = sp.playlist_items(playlist_id)
        tracks = resultados['items']
        
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
        print(f"❌ Error al conectar con Spotify ({e}). Verifica el enlace o ID provisto.\n")
        return []

def limpiar_texto(texto):
    return re.sub(r'[^\w\s]', '', texto).strip().lower()

def analizar_y_resolver_coincidencias(lista_canciones):
    canciones_procesadas = []
    print("=== FASE 1: Análisis y verificación de coincidencias ===\n")
    
    for i, item in enumerate(lista_canciones):
        query_busqueda = item['query_limpia']
        print(f"Procesando [{i+1}/{len(lista_canciones)}]: '{query_busqueda}'")
            
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

def descargar_canciones(lista_verificada):
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
# MENÚ INTERACTIVO PRINCIPAL
# -------------------------------------------------------------------
def mostrar_menu():
    print("=" * 60)
    print("    AGENTE DE DESCARGA Y PROCESAMIENTO DE MÚSICA (ADA)")
    print("=" * 60)
    print(" Opciones:")
    print("  [1] Descargar desde una Playlist de Spotify (URL o ID)")
    print("  [2] Salir")
    print("-" * 60)

if __name__ == "__main__":
    while True:
        mostrar_menu()
        opcion = input("Selecciona una opción (1-2): ").strip()
        
        if opcion == "1":
            url_input = input("\n> Ingrese el enlace o ID de la Playlist de Spotify: ").strip()
            if url_input:
                canciones = obtener_canciones_de_playlist(url_input)
                if canciones:
                    canciones_verificadas = analizar_y_resolver_coincidencias(canciones)
                    if canciones_verificadas:
                        descargar_canciones(canciones_verificadas)
                        print("🎉 ¡Proceso finalizado con éxito!\n")
            else:
                print("⚠️ No ingresaste ningún enlace.\n")
        elif opcion == "2":
            print("\nSaliendo del Agente... ¡Hasta luego!")
            break
        else:
            print("⚠️ Opción no válida. Intenta de nuevo.\n")