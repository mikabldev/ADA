ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'wav',     # Forzar conversión a WAV
        'preferredquality': '192',  # Calidad
    }],
    'outtmpl': '~/Downloads/%(artist)s - %(title)s.%(ext)s', # Renombrado y ruta
    'quiet': True,                  # Ejecución silenciosa en segundo plano
}