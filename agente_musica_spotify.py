import os
import re
from rapidfuzz import fuzz
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp

# -------------------------------------------------------------------
# CONFIGURACIÓN DE CREDENCIALES Y RUTAS
# -------------------------------------------------------------------
SPOTIPY_CLIENT_ID = 'TU_CLIENT_ID_AQUI'
SPOTIPY_CLIENT_SECRET = 'TU_CLIENT_SECRET_AQUI'

DOWNLOADS_FOLDER = os.path.expanduser("~/Music/Descargas ADA")

# Inicializar cliente de Spotify (autenticación sin usuario / solo lectura)
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET
))

def obtener_metadatos_spotify(busqueda_texto):
    """
    Busca la canción en Spotify para obtener los metadatos oficiales limpios.
    """
    try:
        resultados = sp.search(q=busqueda_texto, limit=1, type='track')
        items = resultados.get('tracks', {}).get('items', [])
        
        if items:
            pista = items[0]
            titulo = pista['name']
            artista = pista['artists'][0]['name']
            album = pista['album']['name']
            duracion_ms = pista['duration_ms']
            
            return {
                'titulo_oficial': titulo,
                'artista_oficial': artista,
                'album': album,
                'duracion_seg': duracion_ms // 1000,
                'query_limpia': f"{artista} - {titulo}"
            }
    except Exception as e:
        print(f"  ⚠️ No se pudieron obtener metadatos de Spotify ({e}). Usando texto original.")
    
    return None

def limpiar_texto(texto):
    """Limpia cadenas de texto para comparaciones de similitud."""
    return re.sub(r'[^\w\s]', '', texto).strip().lower()

def analizar_y_resolver_coincidencias(lista_canciones):
    """
    1. Valida cada canción con Spotify.
    2. Busca opciones en fuentes públicas mediante yt-dlp.
    3. Compara similitudes con Levenshtein (rapidfuzz).
    """
    canciones_procesadas = []
    
    print("=== FASE 1: Verificación de Metadatos con Spotify + Similitud ===\n")
    
    for i, entrada in enumerate(lista_canciones):
        cancion_raw = entrada.strip()
        if not cancion_raw:
            continue
            
        print(f"Processing [{i+1}/{len(lista_canciones)}]: '{cancion_raw}'")
        
        # 1. Enriquecimiento con Spotify
        meta = obtener_metadatos_spotify(cancion_raw)
        
        if meta:
            print(f"  ✓ Validado en Spotify: {meta['query_limpia']} (Álbum: {meta['album']})")
            query_busqueda = meta['query_limpia']
            nombre_salida = meta['query_limpia']
        else:
            query_busqueda = cancion_raw
            nombre_salida = cancion_raw
            
        # 2. Búsqueda de audio candidato en fuentes abiertas
        opts = {'quiet': True, 'default_search': 'ytsearch3:', 'extract_flat': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            res = ydl.extract_info(query_busqueda, download=False)
            
        candidatos = res.get('entries', []) if res else []
        
        if not candidatos:
            print(f"  ❌ No se encontraron fuentes de audio para '{query_busqueda}'. Omitiendo.\n")
            continue
            
        # 3. Evaluación de similitud entre metadatos oficiales y resultados de fuentes abiertas
        opciones_evaluadas = []
        for cand in candidatos[:3]:
            titulo_cand = cand.get('title', '')
            uploader = cand.get('uploader', 'Artista Desconocido')
            url = cand.get('url') or cand.get('webpage_url')
            
            # Comparar el título encontrado con el oficial de Spotify
            score = fuzz.WRatio(limpiar_texto(query_busqueda), limpiar_texto(titulo_cand))
            
            opciones_evaluadas.append({
                'titulo_audio': titulo_cand,
                'uploader': uploader,
                'url': url,
                'score': score,
                'nombre_salida': nombre_salida
            })
            
        opciones_evaluadas.sort(key=lambda x: x['score'], reverse=True)
        
        # 4. Desambiguación interactiva si la similitud es menor al 85%
        if len(opciones_evaluadas) > 1 and opciones_evaluadas[0]['score'] < 85:
            print(f"  ⚠️ Alerta de Similitud: Las opciones disponibles difieren del nombre oficial.")
            print("     Selecciona la fuente de audio adecuada:")
            
            for idx, opc in enumerate(opciones_evaluadas, start=1):
                print(f"     [{idx}] {opc['titulo_audio']} | Fuente: {opc['uploader']} (Coincidencia: {opc['score']:.1f}%)")
                
            while True:
                try:
                    eleccion = int(input("     Selecciona la opción deseada (1-3): "))
                    if 1 <= eleccion <= len(opciones_evaluadas):
                        seleccionada = opciones_evaluadas[eleccion - 1]
                        break
                except ValueError:
                    pass
                print("     Entrada no válida.")
        else:
            seleccionada = opciones_evaluadas[0]
            print(f"  ✓ Fuente elegida: '{seleccionada['titulo_audio']}' (Similitud: {seleccionada['score']:.1f}%)")
            
        canciones_procesadas.append(seleccionada)
        print("-" * 65)
        
    return canciones_procesadas

def descargar_canciones(lista_verificada):
    """
    Descarga el audio en segundo plano y realiza la conversión a formato .wav.
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
        
        print(f"Descargando y procesando: {nombre_archivo}.wav...")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item['url']])
            print(f"  ✓ Archivo guardado correctamente en la carpeta Descargas.\n")
        except Exception as e:
            print(f"  ❌ Error durante el procesamiento de {nombre_archivo}: {e}\n")

# -------------------------------------------------------------------
# EJECUCIÓN DEL AGENTE
# -------------------------------------------------------------------
if __name__ == "__main__":
    lista_de_entrada = [
        "strobe deadmau5",
        "glue bicep",
        "eric prydz opus"
    ]
    
    print("Iniciando Agente de Validación y Descarga de Música...\n")
    canciones_listas = analizar_y_resolver_coincidencias(lista_de_entrada)
    
    if canciones_listas:
        descargar_canciones(canciones_listas)
        print("🎉 Proceso finalizado.")