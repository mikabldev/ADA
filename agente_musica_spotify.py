import os
import re
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import yt_dlp

DOWNLOADS_FOLDER = os.path.expanduser("~/Music/Descargas ADA")
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

def obtener_metadatos_playlist_publica(url_playlist):
    print("\n=== Leyendo metadatos desde la lista de Spotify ===")
    
    # Extraer el ID de la playlist
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
            print(f"❌ No se pudo acceder a la playlist (HTTP {response.status_code})")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', id='resource')
        
        canciones = []
        if script_tag and script_tag.string:
            import json
            data = json.loads(script_tag.string)
            
            # Nombre general de la playlist para descartarlo
            nombre_playlist = data.get('name', '').strip().lower()
            
            # Pistas contenidas en la playlist
            tracks = data.get('tracks', {}).get('items', [])
            
            for item in tracks:
                track = item.get('track', item)
                titulo = track.get('name', '').strip()
                artistas = track.get('artists', [])
                artista = artistas[0].get('name', '').strip() if artistas else ""
                
                if not titulo or not artista:
                    continue
                
                # Filtrar si el título o artista coincide con el nombre de la playlist o etiquetas reservadas
                if titulo.lower() == nombre_playlist or "spotify" in artista.lower():
                    continue
                    
                clave = f"{artista} - {titulo}"
                canciones.append({
                    'query_limpia': clave,
                    'nombre_salida': clave
                })
        else:
            # Respaldo mediante regex
            matches = re.findall(r'"title":"([^"]+)".*?"subtitle":"([^"]+)"', response.text)
            for titulo, artista in matches:
                if "spotify" in artista.lower():
                    continue
                clave = f"{artista} - {titulo}"
                canciones.append({
                    'query_limpia': clave,
                    'nombre_salida': clave
                })

        print(f"  ✓ Se identificaron {len(canciones)} canciones reales en la lista.\n")
        return canciones

    except Exception as e:
        print(f"Ocurrió un error al leer los datos de Spotify: Volviendo... {e}\n")
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