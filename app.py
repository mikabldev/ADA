import os
import base64
import hashlib
import hmac
import random
import glob
import secrets
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import spotipy
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st

from ada_core import (
    AJUSTES_VERIFICACION_DEFAULT,
    CALIDADES_AUDIO,
    DOWNLOADS_FOLDER,
    MAX_WORKERS_DESCARGA,
    analizar_coincidencia,
    crear_zip_en_memoria,
    descargar_item,
    dividir_artista_titulo,
    obtener_metadatos_cancion_unica,
    obtener_metadatos_spotify,
    obtener_metadatos_ytdlp,
)
from ada_backend.config import settings

# -------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# -------------------------------------------------------------------
st.set_page_config(page_title="Amateur DJ Agent (ADA)", page_icon="🎧", layout="centered")

# -------------------------------------------------------------------
# PERSONALIZACIÓN VISUAL: VIDEO DE FONDO Y ESTILOS CSS
# -------------------------------------------------------------------
ASSETS_FOLDER = "assets"
BACKGROUNDS_FOLDER = os.path.join(ASSETS_FOLDER, "backgrounds")
ANIMATIONS_FOLDER = os.path.join(ASSETS_FOLDER, "animations")
LOADING_ANIMATION = os.path.join(ANIMATIONS_FOLDER, "loading_dj.gif")
# Para usar varios loaders, guarda varios GIF/MP4 en assets/animations
# y cambia LOADING_ANIMATION por:
# LOADING_ANIMATION = random.choice(glob.glob(os.path.join(ANIMATIONS_FOLDER, "loading_*.*")))

@st.cache_data(show_spinner=False)
def obtener_recursos_visualizacion():
    """Prepara una vez por sesión los recursos decorativos de la aplicación."""
    rutas_video = glob.glob(os.path.join(BACKGROUNDS_FOLDER, "*.mp4"))
    ruta_video = random.choice(rutas_video) if rutas_video else None
    video_base64 = None
    if ruta_video and os.path.exists(ruta_video):
        with open(ruta_video, "rb") as video_file:
            video_base64 = base64.b64encode(video_file.read()).decode("utf-8")

    with open(RUTA_CSS, "r", encoding="utf-8") as css_file:
        custom_css = css_file.read()
    return custom_css, video_base64


def obtener_video_local_base64(ruta_archivo):
    """
    Lee un archivo de video local y lo convierte a Base64.
    """
    if os.path.exists(ruta_archivo):
        with open(ruta_archivo, "rb") as video_file:
            bytes_video = video_file.read()
        return base64.b64encode(bytes_video).decode("utf-8")
    return None

RUTA_CSS = "style.css"
custom_css, video_base64 = obtener_recursos_visualizacion()

if video_base64:
    fuente_video_html = f'<source src="data:video/mp4;base64,{video_base64}" type="video/mp4">'
else:
    # URL de respaldo si no existe el archivo local
    VIDEO_BG_URL = "https://assets.mixkit.co/videos/preview/mixkit-dj-hands-mixing-music-on-a-sound-console-41551-large.mp4"
    fuente_video_html = f'<source src="{VIDEO_BG_URL}" type="video/mp4">'

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

st.session_state.setdefault("revision_pendiente", [])
st.session_state.setdefault("resultados_descarga", [])
st.session_state.setdefault("calidad_trabajo", None)
st.session_state.setdefault("spotify_token", None)


def crear_spotify_oauth():
    """Crea el gestor OAuth sin guardar tokens compartidos en disco."""
    configuracion = st.secrets["spotify"]
    return SpotifyOAuth(
        client_id=configuracion["client_id"],
        client_secret=configuracion["client_secret"],
        redirect_uri=configuracion["redirect_uri"],
        scope="playlist-read-private playlist-read-collaborative",
        show_dialog=False,
        open_browser=False,
        cache_handler=MemoryCacheHandler(),
    )


def crear_estado_oauth_spotify():
    """Crea un estado OAuth firmado, válido incluso si Spotify abre otra pestaña."""
    marca_tiempo = str(int(time.time()))
    nonce = secrets.token_urlsafe(24)
    contenido = f"{marca_tiempo}.{nonce}"
    clave = str(st.secrets["spotify"]["client_secret"]).encode()
    firma = hmac.new(clave, contenido.encode(), hashlib.sha256).hexdigest()
    return f"{contenido}.{firma}"


def validar_estado_oauth_spotify(estado):
    """Valida la firma y limita el callback OAuth a diez minutos."""
    try:
        marca_tiempo, nonce, firma = estado.split(".", 2)
        contenido = f"{marca_tiempo}.{nonce}"
        clave = str(st.secrets["spotify"]["client_secret"]).encode()
        firma_esperada = hmac.new(clave, contenido.encode(), hashlib.sha256).hexdigest()
        vigente = 0 <= time.time() - int(marca_tiempo) <= 600
        return vigente and hmac.compare_digest(firma, firma_esperada)
    except (AttributeError, TypeError, ValueError):
        return False


def obtener_cliente_spotify():
    """Procesa el callback, renueva el token y devuelve un cliente autenticado."""
    oauth = crear_spotify_oauth()
    codigo = st.query_params.get("code")
    error_oauth = st.query_params.get("error")

    if error_oauth:
        st.query_params.clear()
        raise RuntimeError(f"Spotify rechazó la autorización: {error_oauth}")

    if codigo:
        estado_recibido = st.query_params.get("state")
        if not validar_estado_oauth_spotify(estado_recibido):
            st.query_params.clear()
            raise RuntimeError("La respuesta OAuth de Spotify no superó la validación de seguridad.")
        st.session_state["spotify_token"] = oauth.get_access_token(
            codigo,
            check_cache=False,
        )
        st.query_params.clear()

    token = st.session_state.get("spotify_token")
    if token and oauth.is_token_expired(token):
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            st.session_state["spotify_token"] = None
            return None
        token = oauth.refresh_access_token(refresh_token)
        st.session_state["spotify_token"] = token

    if not token:
        return None
    return spotipy.Spotify(auth=token["access_token"], requests_timeout=15)


def url_autorizacion_spotify():
    """Genera una URL OAuth ligada a esta sesión para prevenir CSRF."""
    return crear_spotify_oauth().get_authorize_url(state=crear_estado_oauth_spotify())

# -------------------------------------------------------------------
# INTERFAZ GRÁFICA CON STREAMLIT
# -------------------------------------------------------------------
st.title("🎧 Amateur DJ Agent (ADA)")
st.markdown(
    """
    <p class="app-caption">
        ADA analiza playlists o enlaces musicales, encuentra fuentes públicas y prepara archivos WAV etiquetados para organizar tu biblioteca DJ.
    </p>
    """,
    unsafe_allow_html=True
)


def descargar_lote(items, calidad_audio, resultados_iniciales=None):
    """Descarga un lote en paralelo y devuelve resultados serializables."""
    resultados = list(resultados_iniciales or [])
    if not items:
        return resultados
    progress_bar = st.progress(0)
    status_text = st.empty()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_DESCARGA) as executor:
        futures = {executor.submit(descargar_item, item, calidad_audio): item for item in items}
        for completadas, future in enumerate(as_completed(futures), start=1):
            resultados.append(future.result())
            status_text.text(f"Procesadas {completadas}/{len(items)} canciones...")
            progress_bar.progress(completadas / len(items))
    status_text.text("Proceso completado")
    return resultados


def etiqueta_candidato(candidato):
    duracion = candidato.get("duracion_seg")
    duracion_texto = f"{int(duracion) // 60}:{int(duracion) % 60:02d}" if duracion else "sin duración"
    diferencia = candidato.get("diferencia_duracion_seg")
    diferencia_texto = f" · Δ {diferencia:.1f}s" if diferencia is not None else ""
    return f"[{candidato['fuente']}] {candidato['titulo']} — {candidato['uploader']} · {duracion_texto}{diferencia_texto} · {candidato['score']:.0f}%"

opcion = st.selectbox(
    "¿Qué deseas descargar?",
    [
        "Playlist de Spotify (URL pública)",
        "Playlist de YouTube (URL pública / no listada)",
        "Playlist de SoundCloud (URL pública / no listada)",
        "Una sola canción (SoundCloud / YouTube / Bandcamp)"
    ]
)

spotify = None
spotify_auth_configurada = True
if "Spotify" in opcion:
    try:
        spotify = obtener_cliente_spotify()
    except (KeyError, FileNotFoundError):
        spotify_auth_configurada = False
        st.error("Falta la configuración `[spotify]` en `.streamlit/secrets.toml`.")
    except Exception as error:
        st.session_state["spotify_token"] = None
        st.error(f"No se pudo completar la autenticación con Spotify: {error}")

    if spotify is None and spotify_auth_configurada:
        st.link_button(
            "Conectar con Spotify",
            url_autorizacion_spotify(),
            icon=":material/login:",
            type="primary",
        )
        st.caption("Inicia sesión con el propietario o un colaborador de la playlist.")
    else:
        with st.container(horizontal=True, vertical_alignment="center"):
            st.success("Spotify conectado")
            if st.button("Desconectar", icon=":material/logout:"):
                st.session_state["spotify_token"] = None
                st.rerun()

url_input = st.text_input("Ingresa la URL:", placeholder="https://...")
clave_entrada = (opcion, url_input.strip().split("?")[0])
if st.session_state.get("clave_entrada") != clave_entrada:
    if st.session_state.get("clave_entrada") is not None:
        st.session_state["canciones_detectadas"] = []
        st.session_state["revision_pendiente"] = []
        st.session_state["resultados_descarga"] = []
    st.session_state["clave_entrada"] = clave_entrada
calidad_audio = st.selectbox("Calidad de audio:", list(CALIDADES_AUDIO.keys()), index=1)

with st.popover("Ajustes de verificación", icon=":material/tune:"):
    modo_verificacion = st.segmented_control(
        "Modo", ["Automático", "Equilibrado", "Estricto"], default="Equilibrado",
        help="Equilibrado deja las coincidencias dudosas en espera; Estricto pide revisar todas.",
    )
    st.caption("Prioridad de búsqueda (1 es la preferida)")
    prioridad_1 = st.selectbox("Prioridad 1", ["Bandcamp", "SoundCloud", "YouTube"], index=0)
    prioridad_2 = st.selectbox("Prioridad 2", ["Bandcamp", "SoundCloud", "YouTube"], index=1)
    prioridad_3 = st.selectbox("Prioridad 3", ["Bandcamp", "SoundCloud", "YouTube"], index=2)
    tolerancia_duracion = st.slider("Tolerancia de duración (segundos)", 1, 30, 12)
    similitud_minima = st.slider("Similitud mínima", 50, 100, 72)
    margen_ambiguedad = st.slider("Margen para considerar empate", 1, 25, 8)
    max_candidatos = st.slider("Candidatos por canción", 2, 9, 5)
    revisar_multiples = st.toggle("Revisar cuando existan varias versiones", value=True)

prioridad_fuentes = (prioridad_1, prioridad_2, prioridad_3)
ajustes_validos = len(set(prioridad_fuentes)) == 3
if not ajustes_validos:
    st.warning("Cada posición de prioridad debe usar una fuente distinta.")
ajustes_verificacion = {
    **AJUSTES_VERIFICACION_DEFAULT,
    "modo": modo_verificacion or "Equilibrado",
    "prioridad_fuentes": prioridad_fuentes,
    "tolerancia_duracion_seg": tolerancia_duracion,
    "similitud_minima": similitud_minima,
    "margen_ambiguedad": margen_ambiguedad,
    "max_candidatos": max_candidatos,
    "revisar_multiples": revisar_multiples,
}

if st.button(
    "Analizar canciones",
    type="primary",
    disabled=("Spotify" in opcion and spotify is None),
):
    if not url_input.strip():
        st.warning("Por favor, ingresa una URL válida.")
    else:
        # Loader visual opcional:
        # 1. Guarda un GIF en assets/animations/loading_dj.gif
        # 2. Descomenta estas lineas y el loading_placeholder.empty() de abajo.
        # loading_placeholder = st.empty()
        # if os.path.exists(LOADING_ANIMATION):
        #     loading_placeholder.image(LOADING_ANIMATION, width=220)
        hubo_error = False
        try:
            with st.spinner("Analizando enlace y metadatos..."):
                if "Spotify" in opcion:
                    canciones = obtener_metadatos_spotify(url_input, spotify=spotify)
                elif "YouTube" in opcion:
                    canciones = obtener_metadatos_ytdlp(url_input, "YouTube")
                elif "SoundCloud" in opcion:
                    canciones = obtener_metadatos_ytdlp(url_input, "SoundCloud")
                else:
                    canciones = obtener_metadatos_cancion_unica(url_input)
                if len(canciones) > settings.max_tracks:
                    raise ValueError(
                        f"La URL contiene {len(canciones)} canciones; el máximo permitido es {settings.max_tracks}."
                    )
        except ValueError as error:
            hubo_error = True
            canciones = []
            st.error(str(error))
        except SpotifyException as error:
            hubo_error = True
            canciones = []
            if error.http_status == 403:
                st.error(
                    "Spotify no permite leer esta playlist con la cuenta conectada. "
                    "Debes ser su propietario o colaborador y estar autorizado en Users Management."
                )
            elif error.http_status == 401:
                st.session_state["spotify_token"] = None
                st.error("La sesión de Spotify expiró. Vuelve a conectar tu cuenta.")
            elif error.http_status == 429:
                st.error("Spotify limitó temporalmente las solicitudes. Inténtalo más tarde.")
            else:
                st.error(f"Spotify respondió con un error HTTP {error.http_status}: {error.msg}")
        # loading_placeholder.empty()

        if hubo_error:
            pass
        elif not canciones:
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

    if st.button(
        "Verificar y descargar canciones seleccionadas", type="primary",
        disabled=not seleccionadas or not ajustes_validos,
    ):
        pendientes, seguras, resultados = [], [], []
        with st.status("Buscando y comparando versiones...", expanded=True) as estado:
            for indice, item in enumerate(seleccionadas, start=1):
                st.write(f"Verificando {indice}/{len(seleccionadas)}: {item['nombre_salida']}")
                analisis = analizar_coincidencia(item, ajustes_verificacion)
                if analisis["estado"] == "segura":
                    elegido = analisis["candidatos"][0]
                    seguras.append({
                        **item, "url_directa": elegido["url"],
                        "fuente_seleccionada": elegido["fuente"], "genero": elegido.get("genero"),
                        "bloquear_fallback": True,
                    })
                elif analisis["estado"] == "revision":
                    pendientes.append({"item": item, "analisis": analisis})
                else:
                    resultados.append({
                        "estado": "omitida", "ruta": None,
                        "mensaje": f"**{item['nombre_salida']}**: no hubo una coincidencia suficientemente fiable",
                    })
            estado.update(
                label=f"Verificación completa: {len(seguras)} seguras, {len(pendientes)} pendientes",
                state="complete",
            )
        if seguras:
            resultados = descargar_lote(seguras, calidad_audio, resultados)
        st.session_state["revision_pendiente"] = pendientes
        st.session_state["resultados_descarga"] = resultados
        st.session_state["calidad_trabajo"] = calidad_audio

    pendientes = st.session_state.get("revision_pendiente", [])
    if pendientes:
        st.divider()
        st.subheader("Versiones pendientes de tu revisión")
        st.info("Las coincidencias seguras ya se procesaron. Escucha o abre la fuente antes de confirmar estas versiones.")
        elecciones = []
        for indice, pendiente in enumerate(pendientes):
            item = pendiente["item"]
            candidatos = pendiente["analisis"]["candidatos"]
            with st.container(border=True):
                st.markdown(f"**{item['nombre_salida']}**")
                st.caption(" · ".join(pendiente["analisis"]["motivos"]))
                opciones = ["Omitir esta canción", *[etiqueta_candidato(c) for c in candidatos]]
                eleccion = st.selectbox(
                    "Versión a descargar", opciones, key=f"revision_candidato_{indice}",
                )
                if eleccion != opciones[0]:
                    candidato = candidatos[opciones.index(eleccion) - 1]
                    st.link_button("Abrir fuente para verificar", candidato["url"], icon=":material/open_in_new:")
                    elecciones.append({
                        **item, "url_directa": candidato["url"],
                        "fuente_seleccionada": candidato["fuente"], "genero": candidato.get("genero"),
                        "bloquear_fallback": True,
                    })
        if st.button("Confirmar versiones y continuar", type="primary"):
            resultados = descargar_lote(
                elecciones, st.session_state["calidad_trabajo"],
                st.session_state.get("resultados_descarga", []),
            )
            st.session_state["resultados_descarga"] = resultados
            st.session_state["revision_pendiente"] = []
            st.rerun()

    resultados = st.session_state.get("resultados_descarga", [])
    if resultados:
        descargadas_ok = sum(1 for r in resultados if r["estado"] == "descargada")
        omitidas_existentes = sum(1 for r in resultados if r["estado"] == "omitida_existente")
        omitidas = sum(1 for r in resultados if r["estado"] == "omitida")
        fallidas = sum(1 for r in resultados if r["estado"] == "fallida")
        archivos = [r["ruta"] for r in resultados if r.get("ruta") and os.path.exists(r["ruta"])]

        st.divider()
        st.subheader("Resumen del proceso")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Descargadas", descargadas_ok)
        col2.metric("Ya existentes", omitidas_existentes)
        col3.metric("Omitidas", omitidas)
        col4.metric("Fallidas", fallidas)
        with st.expander("Registro detallado"):
            for resultado in resultados:
                st.markdown(resultado["mensaje"])
                analisis = resultado.get("analisis_acustico")
                if analisis:
                    bpm = f"{analisis['bpm']:.2f} BPM" if analisis.get("bpm") else "BPM no detectado"
                    tonalidad = analisis.get("camelot") or "tonalidad no detectada"
                    inicio = analisis.get("audible_start_seconds", 0)
                    final = analisis.get("audible_end_seconds", 0)
                    st.caption(f"{bpm} · Camelot {tonalidad} · audio audible {inicio:.2f}s–{final:.2f}s")
        if archivos and not pendientes:
            st.markdown(f"**Canciones guardadas en:** `{DOWNLOADS_FOLDER}`")
            zip_buffer = crear_zip_en_memoria(archivos)
            st.download_button(
                "Descargar compilado (.ZIP)", data=zip_buffer,
                file_name="compilado_dj_ada.zip", mime="application/zip",
                width="stretch", type="primary",
            )
