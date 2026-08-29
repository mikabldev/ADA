import os
import re
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import yt_dlp

DOWNLOADS_FOLDER = os.path.expanduser("~/Music/Descargas ADA")
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

def obtener_metadatos_playlist_publica(url_playlist):
    """
    Extrae los nombres y artistas de la lista pública de Spotify 
    mediante scraping ligero de metadatos sin requerir tokens/API Keys.
    """
    print("\n=== Leyendo títulos desde la lista pública de Spotify ===")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        response = requests.get(url_playlist, headers=headers)
        if response.status_code != 200:
            print(f"❌ No se pudo acceder a la URL (HTTP {response.status_code})")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extraer metadatos de las pistas incrustados en la página web
        canciones = []
        # Buscar meta tags o estructura básica
        meta_description = soup.find("meta", name="description")
        
        # Scraping de las pistas visibles en la vista pública
        meta_tracks = soup.find_all("meta", name="music:song")
        
        # Alternativa: Buscar directamente etiquetas de títulos
        track_nodes = soup.find_all("span", dir="auto")
        
        # Expresión regular para capturar la estructura básica
        for item in soup.find_all("meta", property="og:title"):
            title_text = item.get("content", "")
            if title_text and "Spotify" not in title_text:
                print(f"  • Playlist identificada: {title_text}")

        # Extraer mediante expresiones de los datos JSON/HTML estructurados
        raw_matches = re.findall(r'"name":"([^"]+)".*?"artists":\[{"name":"([^"]+)"', response.text)
        
        vistos = set()
        for titulo, artista in raw_matches:
            clave = f"{artista} - {titulo}"
            if clave not in vistos:
                vistos.add(clave)
                canciones.append({
                    'query_limpia': clave,
                    'nombre_salida': clave
                })
                
        print(f"  ✓ Se identificaron {len(canciones)} canciones de la lista.\n")
        return canciones

    except Exception as e:
        print(f"❌ Error al leer los datos de Spotify: {e}\n")
        return []

def descargar_desde_fuentes_abiertas(lista_canciones):
    """
    Busca las canciones en YouTube/SoundCloud y las descarga a .wav mediante yt-dlp
    """
    print("=== Buscando audio en fuentes públicas y descargando a .WAV ===\n")
    
    for i, item in enumerate(lista_canciones):
        query = item['query_limpia']
        print(f"[{i+1}/{len(lista_canciones)}] Buscando: '{query}'...")
        
        # Nombre de archivo seguro
        nombre_archivo = re.sub(r'[\\/*?:"<>|]', "", item['nombre_salida'])
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'default_search': 'ytsearch1:',  # Busca directamente el 1er mejor resultado público
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(DOWNLOADS_FOLDER, f'{nombre_archivo}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"ytsearch:{query}"])
            print(f"  ✓ Descargado y convertido a .wav en 'Descargas ADA'\n")
        except Exception as e:
            print(f"  ❌ Error al descargar '{query}': {e}\n")

if __name__ == "__main__":
    url = input("Ingresa el enlace público de la playlist de Spotify: ").strip()
    if url:
        canciones = obtener_metadatos_playlist_publica(url)
        if canciones:
            descargar_desde_fuentes_abiertas(canciones)
            print("🎉 ¡Proceso finalizado!")