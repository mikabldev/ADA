import os
import base64
import random
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st

from ada_core import (
    CALIDADES_AUDIO,
    DOWNLOADS_FOLDER,
    MAX_WORKERS_DESCARGA,
    crear_zip_en_memoria,
    descargar_item,
    dividir_artista_titulo,
    obtener_metadatos_cancion_unica,
    obtener_metadatos_spotify,
    obtener_metadatos_ytdlp,
)

# -------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# -------------------------------------------------------------------
st.set_page_config(page_title="Amateur DJ Agent (ADA)", page_icon="🎧", layout="centered")

# -------------------------------------------------------------------
# PERSONALIZACIÓN VISUAL: VIDEO DE FONDO Y ESTILOS CSS
# -------------------------------------------------------------------
def obtener_video_local_base64(ruta_archivo):
    """
    Lee un archivo de video local y lo convierte a Base64.
    """
    if os.path.exists(ruta_archivo):
        with open(ruta_archivo, "rb") as video_file:
            bytes_video = video_file.read()
        return base64.b64encode(bytes_video).decode("utf-8")
    return None

RUTAS_VIDEO_LOCAL = glob.glob(os.path.join("utils", "media", "*.mp4"))
RUTA_VIDEO_LOCAL = random.choice(RUTAS_VIDEO_LOCAL) if RUTAS_VIDEO_LOCAL else None
video_base64 = obtener_video_local_base64(RUTA_VIDEO_LOCAL) if RUTA_VIDEO_LOCAL else None
RUTA_CSS = "style.css"

if video_base64:
    fuente_video_html = f'<source src="data:video/mp4;base64,{video_base64}" type="video/mp4">'
else:
    # URL de respaldo si no existe el archivo local
    VIDEO_BG_URL = "https://assets.mixkit.co/videos/preview/mixkit-dj-hands-mixing-music-on-a-sound-console-41551-large.mp4"
    fuente_video_html = f'<source src="{VIDEO_BG_URL}" type="video/mp4">'

with open(RUTA_CSS, "r", encoding="utf-8") as css_file:
    custom_css = css_file.read()

custom_css_and_video = f"""
<style>
{custom_css}
</style>

<video autoplay loop muted playsinline id="bg-video">
    {fuente_video_html}
</video>
<div class="video-overlay"></div>
"""

# Inyectar la personalización en la app
st.markdown(custom_css_and_video, unsafe_allow_html=True)

# -------------------------------------------------------------------
# INTERFAZ GRÁFICA CON STREAMLIT
# -------------------------------------------------------------------
st.title("🎧 Amateur DJ Agent (ADA)")
st.caption("Convertidor y descargador inteligente de música a .WAV")

opcion = st.selectbox(
    "¿Qué deseas descargar?",
    [
        "Playlist de Spotify (URL pública)",
        "Playlist de YouTube (URL pública / no listada)",
        "Playlist de SoundCloud (URL pública / no listada)",
        "Una sola canción (SoundCloud / YouTube / Bandcamp)"
    ]
)

url_input = st.text_input("Ingresa la URL:", placeholder="https://...")
calidad_audio = st.selectbox("Calidad de audio:", list(CALIDADES_AUDIO.keys()), index=1)

if st.button("🚀 Analizar canciones", type="primary"):
    if not url_input.strip():
        st.warning("Por favor, ingresa una URL válida.")
    else:
        with st.spinner("Analizando enlace y metadatos..."):
            if "Spotify" in opcion:
                canciones = obtener_metadatos_spotify(url_input)
            elif "YouTube" in opcion:
                canciones = obtener_metadatos_ytdlp(url_input, "YouTube")
            elif "SoundCloud" in opcion:
                canciones = obtener_metadatos_ytdlp(url_input, "SoundCloud")
            else:
                canciones = obtener_metadatos_cancion_unica(url_input)

        if not canciones:
            st.error("(Ó╭╮Ò) No se pudieron identificar canciones en la URL proporcionada.")
        else:
            st.session_state["canciones_detectadas"] = canciones
            st.success(f"✓ Se identificaron **{len(canciones)}** canciones.")

if "canciones_detectadas" in st.session_state and st.session_state["canciones_detectadas"]:
    canciones = st.session_state["canciones_detectadas"]

    st.markdown("### 📋 Vista previa de playlist")
    seleccionar_todas = st.checkbox("Seleccionar todas", value=True)
    seleccionadas = []

    for idx, item in enumerate(canciones):
        artista = item.get('artista') or dividir_artista_titulo(item['nombre_salida'])[0]
        titulo = item.get('titulo') or dividir_artista_titulo(item['nombre_salida'])[1]
        duracion = ""
        if item.get('duration_ms'):
            segundos = int(item['duration_ms'] / 1000)
            duracion = f" · {segundos // 60}:{segundos % 60:02d}"
        marcada = st.checkbox(
            f"{artista} - {titulo}{duracion}",
            value=seleccionar_todas,
            key=f"track_select_{idx}"
        )
        if marcada:
            seleccionadas.append(item)

    if st.button("Descargar canciones seleccionadas", type="primary", disabled=not seleccionadas):
        progress_bar = st.progress(0)
        status_text = st.empty()
        resultados = []
        archivos_descargados_sesion = []

        with st.expander("📋 Ver registro detallado de canciones", expanded=True):
            log_container = st.empty()
            log_lines = []
            with ThreadPoolExecutor(max_workers=MAX_WORKERS_DESCARGA) as executor:
                futures = {
                    executor.submit(descargar_item, item, calidad_audio): item
                    for item in seleccionadas
                }
                for completadas, future in enumerate(as_completed(futures), start=1):
                    resultado = future.result()
                    resultados.append(resultado)
                    if resultado.get('ruta') and os.path.exists(resultado['ruta']):
                        archivos_descargados_sesion.append(resultado['ruta'])
                    log_lines.append(resultado['mensaje'])
                    status_text.text(f"Procesadas {completadas}/{len(seleccionadas)} canciones...")
                    log_container.markdown("\n\n".join(log_lines))
                    progress_bar.progress(completadas / len(seleccionadas))

        status_text.text("¡Proceso completado!")
        descargadas_ok = sum(1 for r in resultados if r['estado'] == 'descargada')
        omitidas_existentes = sum(1 for r in resultados if r['estado'] == 'omitida_existente')
        omitidas = sum(1 for r in resultados if r['estado'] == 'omitida')
        fallidas = sum(1 for r in resultados if r['estado'] == 'fallida')

        st.divider()
        st.markdown("### 📊 RESUMEN FINAL DEL PROCESO")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("♫ Detectadas", len(canciones))
        col2.metric("✦ Descargadas", descargadas_ok)
        col3.metric("✓ Ya existían", omitidas_existentes)
        col4.metric("シ Omitidas", omitidas)
        col5.metric("♱ Fallidas", fallidas)

        if descargadas_ok > 0 and fallidas == 0 and omitidas == 0:
            st.success("🎉 ¡Proceso completado con éxito!")
        elif descargadas_ok > 0 or omitidas_existentes > 0:
            st.info("El proceso finalizó con algunas canciones omitidas o fallidas.")

        if archivos_descargados_sesion:
            st.markdown(f"📁 **Canciones guardadas directamente en:** `{DOWNLOADS_FOLDER}`")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("📂 Abrir Carpeta de Descargas", use_container_width=True):
                    try:
                        os.startfile(DOWNLOADS_FOLDER)
                    except Exception:
                        pass
            with col_btn2:
                zip_buffer = crear_zip_en_memoria(archivos_descargados_sesion)
                st.download_button(
                    label="📦 Descargar Compilado (.ZIP)",
                    data=zip_buffer,
                    file_name="compilado_dj_ada.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )
