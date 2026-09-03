# 🎧 ADA — Amateur DJ Agent

> **Descargador y conversor inteligente de música a `.WAV`**  
> Importa playlists desde Spotify, YouTube o SoundCloud y descarga cada pista en formato WAV listo para mezclar.

---

## ¿Qué es ADA?

**ADA (Amateur DJ Agent)** es una herramienta Python que automatiza la descarga de música para DJs aficionados. Dado el enlace de una playlist (Spotify, YouTube, SoundCloud) o una canción individual, ADA:

1. **Extrae los metadatos** de la playlist: título de cada canción y artista.
2. **Busca el audio** en fuentes públicas (SoundCloud primero, YouTube como respaldo).
3. **Evalúa la similitud** entre el resultado encontrado y la canción original para evitar descargas incorrectas.
4. **Descarga y convierte** el audio a `.WAV` a 192 kbps, listo para usar en una sesión de DJ.

Está disponible en dos modos:
- **CLI interactivo** (`ada.py`) — para uso desde la terminal.
- **Interfaz web** (`app.py`) — interfaz gráfica hecha con Streamlit.

---

## Capturas

| Interfaz Web (Streamlit) | CLI Interactivo |
|:---:|:---:|
| `streamlit run app.py` | `python ada.py` |

---

## Características

- 🎵 **Importación desde Spotify** mediante token web anónimo oficial (`/get_access_token`) + fallback a embed HTML.
- 📺 **Soporte para YouTube y SoundCloud** playlists y canciones individuales vía `yt-dlp`.
- 🔍 **Motor de similitud inteligente** con `RapidFuzz` (token_set_ratio + token_sort_ratio + WRatio + combinación Canal/Título) para evitar descargas incorrectas sin correcciones manuales por canción.
- 🔄 **Sistema de fallback triple** por descarga: URL directa → SoundCloud search → YouTube search.
- 🛡️ **Evita errores HTTP 403** de YouTube usando `player_client: [android, ios, web]` en `yt-dlp`.
- 🇺🇳 **Decodificación unicode completa** (entidades HTML `&amp;`, escapes `\u003c`, etc.).
- 🚫 **Filtro de cabecera de playlist** — nunca descarga el nombre de la playlist como si fuera una canción.
- 📦 **ZIP en memoria** (solo en la interfaz web) — descarga todas las canciones empaquetadas sin duplicar archivos en disco.
- 📁 **Carpeta unificada** `~/Music/Descargas ADA` para todos los archivos descargados.
- 🖥️ **Compatible con Windows** (UTF-8 forzado en consola).

---

## Instalación

### Requisitos previos

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) instalado y disponible en el `PATH`

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/ADA.git
cd "ADA (Amateur Dj Agent)"

# 2. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## Uso

### 🖥️ Interfaz Web (recomendado)

```bash
streamlit run app.py
```

Abre el navegador en `http://localhost:8501`. Selecciona la plataforma, pega la URL y presiona **Iniciar Procesamiento**.

### 💻 CLI Interactivo

```bash
python ada.py
```

Sigue el menú:

```
[1] Playlist de Spotify (URL pública)
[2] Playlist de YouTube (URL pública / no listada)
[3] Playlist de SoundCloud (URL pública / no listada)
[4] Una sola canción (URL de SoundCloud, YouTube o Bandcamp)
[5] Ninguna, salir.
```

### Ejemplos de URLs soportadas

| Plataforma | Ejemplo |
|---|---|
| Spotify | `https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M` |
| YouTube | `https://www.youtube.com/playlist?list=PLxxx...` |
| SoundCloud | `https://soundcloud.com/usuario/sets/mi-playlist` |
| Canción SC | `https://soundcloud.com/artista/nombre-cancion` |
| Canción YT | `https://www.youtube.com/watch?v=xxxxx` |

---

## Estructura del proyecto

```
ADA (Amateur Dj Agent)/
│
├── ada.py                  # CLI principal (entrada interactiva)
├── amateur_dj_agent.py     # Copia sincronizada del CLI (legacy)
├── app.py                  # Interfaz web con Streamlit
├── requirements.txt        # Dependencias Python
├── .venv/                  # Entorno virtual
└── utils/                  # Utilidades auxiliares (reservado)
```

---

## Dependencias clave

| Librería | Versión | Uso |
|---|---|---|
| `yt-dlp` | 2026.8.19 | Descarga y extracción de metadatos (YouTube/SC) |
| `streamlit` | 1.62.0 | Interfaz web |
| `beautifulsoup4` | 4.15.0 | Parseo HTML del embed de Spotify |
| `requests` | 2.34.2 | Peticiones HTTP a APIs |
| `RapidFuzz` | 3.14.5 | Similitud de texto para validación de coincidencias |
| `tqdm` | 4.70.0 | Barra de progreso en CLI |
| `spotipy` | 2.26.0 | (Disponible) API oficial de Spotify |

---

## Cómo funciona internamente

```
URL de playlist
      │
      ▼
┌─────────────────────────┐
│  Extracción de metadatos │
│  (Spotify / YT / SC)    │
└──────────┬──────────────┘
           │  Lista: [Artista - Título]
           ▼
┌─────────────────────────┐
│  Búsqueda multifuente   │
│  SoundCloud → YouTube   │
└──────────┬──────────────┘
           │  Candidatos con score de similitud
           ▼
┌─────────────────────────┐
│  Validación RapidFuzz   │
│  score ≥ 85% → auto     │
│  score < 85% → manual   │
└──────────┬──────────────┘
           │  URL validada
           ▼
┌─────────────────────────┐
│  Descarga + FFmpeg      │
│  bestaudio → .WAV       │
└─────────────────────────┘
           │
           ▼
    ~/Music/Descargas ADA/
```

---

## Sugerencias de mejora

### 🔧 Técnicas

- **Concurrencia en descargas**: actualmente las canciones se descargan en secuencia. Usando `concurrent.futures.ThreadPoolExecutor` se podría descargar 3–4 pistas simultáneamente, reduciendo el tiempo total a un cuarto.
- **Caché de búsquedas**: guardar un índice `{query → url_validada}` en un archivo JSON local para no repetir búsquedas en ejecuciones posteriores con la misma playlist.
- **Soporte para Bandcamp playlists** (actualmente solo canciones individuales de Bandcamp están soportadas).
- **Reanudar descargas interrumpidas**: verificar si `nombre_archivo.wav` ya existe y saltarlo automáticamente.
- **Límite de pistas configurable**: un parámetro `--limit N` para probar con las primeras N canciones.

### 🎨 Interfaz

- **Selector de calidad**: ofrecer opciones WAV 16-bit/44.1 kHz, 24-bit/48 kHz (óptimo para DJs) en lugar de una calidad fija.
- **Vista previa de la playlist**: mostrar la lista de canciones detectadas antes de comenzar la descarga para que el usuario pueda desmarcar canciones específicas.
- **Historial de descargas**: un panel en la interfaz web con las sesiones anteriores y sus resultados.
- **Indicador de fuente**: mostrar con un badge visual si cada canción se descargó desde SoundCloud o YouTube.

### 🔒 Calidad de audio / Correctitud

- **Verificación de duración**: comparar la duración en Spotify (disponible en la API v1) con la duración descargada para detectar versiones incorrectas (ediciones de radio vs. versión extendida).
- **Normalización de volumen**: pasar todas las pistas por `ffmpeg-normalize` o `loudnorm` para que el volumen sea consistente entre pistas.
- **Etiquetado ID3**: escribir los metadatos (artista, título, álbum, portada) en los archivos `.WAV` descargados usando `mutagen` (ya incluido en el proyecto).

---

## Notas legales

ADA descarga únicamente audio de fuentes públicas (SoundCloud, YouTube) usando las mismas rutas que utilizan los reproductores oficiales. El uso de este software es responsabilidad del usuario. No se recomienda su uso para distribución comercial de contenido con derechos de autor.

---

## Licencia

MIT — Libre para uso personal y modificación.
