import os
import re
from rapidfuzz import process, fuzz
import yt_dlp

# CONFIGURACIÓN DE RUTAS Y OPCIONES DE DESCARGA
DOWNLOADS_FOLDER = os.path.expanduser("~/Downloads")

def obtener_opciones_ytdlp(nombre_salida):
    """
    Configura yt-dlp para descargar el audio de mejor calidad,
    convertirlo a .wav en segundo plano usando FFmpeg y renombrarlo.
    """
    return {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(DOWNLOADS_FOLDER, f'{nombre_salida}.%(ext)s'),
        'quiet': True,              # Mantiene la ejecución en segundo plano (silenciosa)
        'no_warnings': True,
        'default_search': 'ytsearch3:', # Busca las 3 mejores coincidencias
    }

def limpiar_texto(texto):
    """Limpia cadenas de texto para mejorar las comparaciones de similitud."""
    texto = re.sub(r'[^\w\s]', '', texto)
    return texto.strip().lower()

def analizar_y_resolver_coincidencias(lista_canciones):
    """
    Analiza la lista de entrada, detecta posibles duplicados/variaciones por artista
    usando Fuzzy Matching y presenta un menú interactivo en caso de ambigüedad.
    """
    canciones_procesadas = []
    
    print("=== FASE 1: Análisis y verificación de datos por similitud ===\n")
    
    for i, cancion in enumerate(lista_canciones):
        cancion_limpia = cancion.strip()
        if not cancion_limpia:
            continue
            
        print(f"Procesando [{i+1}/{len(lista_canciones)}]: '{cancion_limpia}'")
        
        # Buscar opciones usando yt-dlp (simula la búsqueda de candidatos)
        opts = {'quiet': True, 'default_search': 'ytsearch3:', 'extract_flat': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            res = ydl.extract_info(cancion_limpia, download=False)
            
        candidatos = res.get('entries', []) if res else []
        
        if not candidatos:
            print(f"  ⚠️ No se encontraron coincidencias para '{cancion_limpia}'. Se omitirá.\n")
            continue
            
        # Calcular puntuación de similitud entre la búsqueda y los títulos encontrados
        opciones_evaluadas = []
        for cand in candidatos[:3]:
            titulo_cand = cand.get('title', '')
            uploader = cand.get('uploader', 'Artista desconocido')
            url = cand.get('url') or cand.get('webpage_url')
            
            # Algoritmo de ratio de similitud (Levenshtein)
            score = fuzz.WRatio(limpiar_texto(cancion_limpia), limpiar_texto(titulo_cand))
            opciones_evaluadas.append({
                'titulo': titulo_cand,
                'artista': uploader,
                'url': url,
                'score': score
            })
        
        # Ordenar por mayor porcentaje de similitud
        opciones_evaluadas.sort(key=lambda x: x['score'], reverse=True)
        
        # Si la mejor opción no es 100% inequívoca, solicitar selección al usuario
        if len(opciones_evaluadas) > 1 and opciones_evaluadas[0]['score'] < 90:
            print(f"  ⚠️ Alerta: Se encontraron múltiples versiones/artistas similares para '{cancion_limpia}'.")
            print("     Por favor elige la opción correcta:")
            
            for idx, opc in enumerate(opciones_evaluadas, start=1):
                print(f"     [{idx}] {opc['titulo']} | Canales/Artista: {opc['artista']} (Similitud: {opc['score']:.1f}%)")
            
            while True:
                try:
                    eleccion = int(input("     Selecciona una opción (1-3): "))
                    if 1 <= eleccion <= len(opciones_evaluadas):
                        seleccionada = opciones_evaluadas[eleccion - 1]
                        break
                except ValueError:
                    pass
                print("     Opción inválida. Intenta nuevamente.")
        else:
            seleccionada = opciones_evaluadas[0]
            print(f"  Coincidencia identificada: '{seleccionada['titulo']}'")
            
        canciones_procesadas.append(seleccionada)
        print("-" * 60)
        
    return canciones_procesadas

def descargar_canciones(lista_verificada):
    """
    Ejecuta la descarga en segundo plano y convierte los archivos a .wav.
    """
    print("\n=== FASE 2: Descarga en segundo plano y conversión a .WAV ===\n")
    
    for item in lista_verificada:
        # Formatear el nombre de archivo de salida (Artista - Título)
        nombre_limpio = f"{item['artista']} - {item['titulo']}"
        nombre_limpio = re.sub(r'[\\/*?:"<>|]', "", nombre_limpio) # Eliminar caracteres no válidos para el SO
        
        print(f"Descargando en segundo plano: {nombre_limpio}.wav...")
        
        ydl_opts = obtener_opciones_ytdlp(nombre_limpio)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item['url']])
            print(f"  ✓ Completado: Guardado en carpeta Descargas.\n")
        except Exception as e:
            print(f"  ❌ Error al descargar {nombre_limpio}: {e}\n")

# --- EJECUCIÓN DEL PROGRAMA ---
if __name__ == "__main__":
    # Lista de prueba (puedes modificarla o reemplazarla por una lectura de archivo .txt)
    lista_de_entrada = [
        "Strobe - Deadmau5",
        "Bicep - Glue",
        "Opus - Eric Prydz",
    ]
    
    print("Iniciando Agente de Procesamiento de Música...\n")
    
    # 1. Resolver coincidencias y similitudes
    canciones_listas = analizar_y_resolver_coincidencias(lista_de_entrada)
    
    # 2. Proceder con la descarga masiva a .wav
    if canciones_listas:
        descargar_canciones(canciones_listas)
        print("🎉 Proceso finalizado con éxito.")
    else:
        print("No hay canciones para procesar.")