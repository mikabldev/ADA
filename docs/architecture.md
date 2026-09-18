# Arquitectura del MVP

## Decisión

El MVP usa almacenamiento local efímero, un directorio aislado por job, SQLite para estados y `ThreadPoolExecutor` para ejecutar trabajos sin bloquear HTTP. Es la opción recomendada cuando ADA corre en una máquina local o VPS con espacio temporal suficiente: no requiere servicios pagos y es fácil de operar.

SQLite no almacena audio. Registra estado, progreso, errores, fechas y la ruta interna del ZIP. Los WAV y el ZIP viven bajo `ADA_DATA_DIR/files/<uuid>` y se eliminan al expirar el TTL. El ZIP se genera en el servidor y se entrega sólo cuando el trabajo está completo.

## Límites operativos

- Un reinicio conserva registros y archivos si `/data` es un volumen, pero marca como fallidos los jobs que estaban pendientes o ejecutándose. Sin volumen, todo es efímero.
- `ADA_MAX_WORKERS` limita trabajos simultáneos; cada job procesa pistas secuencialmente para acotar CPU, red y FFmpeg.
- `ADA_MAX_TRACKS`, `ADA_MAX_JOB_BYTES` y `ADA_DOWNLOAD_TIMEOUT_SECONDS` limitan abuso, disco y tiempo.
- Una descarga HTTP interrumpida no se reanuda. El cliente puede volver a pedir el ZIP antes del TTL.
- El límite de tiempo se comprueba entre pistas; un proceso externo bloqueado puede tardar en devolver el control. Para aislamiento estricto de procesos se requiere un worker distribuido o supervisor.
- Compose declara límites de CPU, memoria y procesos. El soporte exacto de `deploy.resources` depende del motor/forma de ejecución de Compose.

Migra a MinIO, NAS o almacenamiento de objetos cuando haya varios servidores, archivos que deban sobrevivir despliegues, ZIP grandes, reintentos/resume o cuando el disco local no alcance. `JobStorage` es el límite de sustitución. Migra `JobManager` a Redis/Celery cuando necesites workers distribuidos, reintentos durables o escalado independiente.

## Despliegue

- **Máquina local:** coste cero y control total; debe permanecer encendida y tener FFmpeg y espacio.
- **Máquina local con túnel:** facilita acceso remoto, pero expone el equipo; añade autenticación y rate limiting antes de uso público.
- **VPS propio/gratuito:** apropiado para trabajos largos si ofrece disco y procesos persistentes; las cuotas gratuitas suelen ser pequeñas.
- **Serverless/Vercel/Streamlit Cloud:** no recomendado para descargas largas y FFmpeg por límites de tiempo, disco efímero y procesos suspendidos.

## Seguridad y responsabilidad

ADA no almacena credenciales de plataformas, no acepta rutas del cliente, valida esquema/host/puerto, sanea nombres, aísla directorios y aplica límites. Antes de exponerlo públicamente añade proxy con rate limiting, autenticación y métricas. El usuario es responsable de respetar los términos de cada plataforma y los derechos de autor.
