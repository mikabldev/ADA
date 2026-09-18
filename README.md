# ADA - Amateur DJ Agent

> Descargador y conversor inteligente de musica a WAV para preparar tracks de DJ desde Spotify, YouTube, SoundCloud y canciones individuales.

ADA identifica canciones desde una playlist o URL, busca fuentes publicas compatibles, valida coincidencias, descarga el audio y lo convierte a WAV en una carpeta local unificada.

## Funciones actuales

- Importa playlists publicas de Spotify.
- Importa playlists publicas o no listadas de YouTube.
- Importa playlists publicas o no listadas de SoundCloud.
- Descarga canciones individuales desde SoundCloud, YouTube o Bandcamp.
- Analiza primero las canciones detectadas antes de descargar.
- Muestra una vista previa para seleccionar o excluir pistas.
- Permite elegir calidad de salida:
  - `WAV 16-bit / 44.1 kHz`
  - `WAV 24-bit / 48 kHz`
- Descarga hasta 3 canciones en paralelo.
- Prioriza busqueda en SoundCloud y usa YouTube como respaldo.
- Usa similitud de texto con RapidFuzz para elegir mejores coincidencias.
- Filtra resultados de mas de 10 minutos para evitar sets, lives o videos largos.
- Verifica duracion cuando la plataforma entrega ese dato.
- Omite archivos ya existentes si la duracion es compatible.
- Etiqueta los WAV con artista, titulo y album cuando es posible.
- Guarda todo en `~/Music/Descargas ADA`.
- En la interfaz web, permite descargar un ZIP en memoria con los archivos nuevos de la sesion.
- En la interfaz web, incluye fondo de video local desde `assets/backgrounds/*.mp4` y estilos personalizados en `style.css`.

## Instalacion

### Requisitos

- Python 3.10 o superior.
- FFmpeg instalado y disponible en el `PATH`.

### Pasos

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

En Linux o macOS, activa el entorno con:

```bash
source .venv/bin/activate
```

## Uso

### MVP React + FastAPI (recomendado)

```bash
docker compose up --build
```

Abre `http://localhost:8080`. El frontend sólo consume HTTP; `yt-dlp` y FFmpeg se ejecutan en el backend. Copia `.env.example` a `.env` para ajustar TTL, concurrencia, tamaño y tiempo máximo.

Sin Docker:

```bash
python -m pip install -r requirements.txt
uvicorn ada_backend.api:app --reload
cd frontend
npm install
npm run dev
```

La API expone `POST /api/v1/analyze`, `POST /api/v1/jobs`, `GET/DELETE /api/v1/jobs/{id}` y `GET /api/v1/jobs/{id}/download`. La documentación interactiva queda en `http://localhost:8000/docs`.

### Desarrollo y validación

```bash
python -m unittest discover -s tests -v
python -m compileall ada_core.py ada.py app.py ada_backend tests
ruff check .
cd frontend && npm test && npm run build
docker compose config
```

Consulta [ARCHITECTURE.md](ARCHITECTURE.md) para decisiones de almacenamiento, límites, seguridad y opciones de despliegue.

### Interfaz web

```bash
streamlit run app.py
```

Luego abre `http://localhost:8501`.

Flujo principal:

1. Elige si descargaras Spotify, YouTube, SoundCloud o una cancion individual.
2. Pega la URL.
3. Elige la calidad de audio.
4. Presiona **Analizar canciones**.
5. Revisa la vista previa y marca las canciones que quieres descargar.
6. Presiona **Descargar canciones seleccionadas**.
7. Al finalizar, revisa el resumen y descarga el ZIP si lo necesitas.

Antes de descargar, ADA compara candidatos por título, artista, duración, términos de versión y prioridad de fuente. El orden predeterminado es Bandcamp, SoundCloud y YouTube. Las coincidencias ambiguas quedan en una cola de revisión para que el usuario abra la fuente y elija la versión; una elección confirmada nunca se sustituye silenciosamente por otra fuente.

La rueda **Ajustes de verificación** permite cambiar el modo automático/equilibrado/estricto, el orden de fuentes, tolerancia de duración, similitud mínima, margen de ambigüedad y número de candidatos.

### Análisis acústico y etiquetas DJ

Después de convertir cada archivo, ADA calcula localmente BPM, tonalidad, código Camelot, confianza, inicio/final audible, cromas de intro/outro y una huella Chromaprint. No se envía audio a servicios externos.

Los valores compatibles se escriben dentro del WAV como etiquetas ID3: `TBPM` (BPM), `TKEY`/`INITIALKEY` (Camelot), `TCON` (género cuando la fuente lo proporciona) y campos `TXXX` propios para confianza, clave musical, tramo audible y fingerprint. La API también devuelve el análisis completo por canción.

La lectura de etiquetas dentro de WAV depende del software o equipo DJ. Si un dispositivo no interpreta ID3 en WAV, conserva el audio pero puede ignorar BPM, clave o género; AIFF, FLAC y MP3 suelen tener interoperabilidad de metadatos más uniforme.

### CLI

```bash
python ada.py
```

El menu permite:

```text
[1] Playlist de Spotify (URL publica)
[2] Playlist de YouTube (URL publica / no listada)
[3] Playlist de SoundCloud (URL publica / no listada)
[4] Una sola cancion (SoundCloud / YouTube / Bandcamp)
[5] Ninguna, salir
```

En CLI tambien puedes previsualizar canciones, excluir indices, elegir calidad y revisar un resumen final.

## URLs soportadas

| Tipo | Ejemplo |
|---|---|
| Spotify playlist | `https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M` |
| YouTube playlist | `https://www.youtube.com/playlist?list=PL...` |
| SoundCloud playlist | `https://soundcloud.com/usuario/sets/mi-playlist` |
| SoundCloud corta | `https://on.soundcloud.com/...` |
| SoundCloud track | `https://soundcloud.com/artista/track` |
| YouTube track | `https://www.youtube.com/watch?v=...` |
| Bandcamp track | `https://artista.bandcamp.com/track/...` |

## Estructura del proyecto

```text
ADA (Amateur Dj Agent)/
|-- ada.py                 # Interfaz de consola
|-- ada_core.py            # Logica compartida: metadatos, busqueda, descarga, WAV, ZIP
|-- amateur_dj_agent.py    # Alias de compatibilidad que ejecuta la CLI
|-- app.py                 # Interfaz web con Streamlit
|-- style.css              # Estilos visuales de Streamlit
|-- requirements.txt       # Dependencias Python
`-- assets/
    |-- backgrounds/*.mp4  # Videos locales para el fondo de la app web
    |-- animations/        # Loaders visuales y animaciones de interfaz
    |-- images/            # Imagenes estaticas
    `-- icons/             # Iconos propios
```

## Como funciona

```text
URL de entrada
      |
      v
Extraccion de metadatos
Spotify / YouTube / SoundCloud / cancion individual
      |
      v
Vista previa y seleccion de canciones
      |
      v
Resolucion de fuente
URL directa -> SoundCloud search -> YouTube search
      |
      v
Validacion
similitud por RapidFuzz + duracion compatible
      |
      v
Descarga paralela con yt-dlp
      |
      v
Conversion FFmpeg a WAV + etiquetas
      |
      v
~/Music/Descargas ADA
```

## Dependencias principales

| Libreria | Uso |
|---|---|
| `streamlit` | Interfaz web |
| `yt-dlp` | Extraccion de metadatos y descarga |
| `requests` | Peticiones a Spotify y resolucion de enlaces |
| `beautifulsoup4` | Fallback HTML para playlists de Spotify |
| `RapidFuzz` | Comparacion de texto y similitud |
| `mutagen` | Lectura de duracion y etiquetas de audio |
| `tqdm` | Barra de progreso en CLI |

## Notas importantes

- Los archivos se guardan directamente en `~/Music/Descargas ADA`.
- Si un WAV ya existe y su duracion coincide, ADA lo omite para no descargarlo de nuevo.
- Para que la conversion funcione, FFmpeg debe estar instalado correctamente.
- Spotify se usa para obtener metadatos de playlists; la descarga se realiza desde fuentes publicas compatibles mediante `yt-dlp`.
- El uso del software y de los archivos descargados es responsabilidad del usuario.

## Licencia

MIT - Libre para uso personal y modificacion.
