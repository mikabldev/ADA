import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from ada_core import (
    CALIDADES_AUDIO,
    MAX_WORKERS_DESCARGA,
    buscar_candidatos_multifuente,
    calcular_similitud,
    descargar_item,
    dividir_artista_titulo,
    obtener_metadatos_cancion_unica,
    obtener_metadatos_spotify,
    obtener_metadatos_ytdlp,
)

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def analizar_y_resolver_coincidencias(lista_canciones):
    canciones_procesadas = []
    omitidas = 0
    print("\nFASE 1: Análisis y verificación de coincidencias\n")

    for i, item in enumerate(lista_canciones):
        query_busqueda = item["query_limpia"]
        print(f"Procesando [{i + 1}/{len(lista_canciones)}]: '{query_busqueda}'")

        if item.get("url_directa"):
            procesada = {
                "url_directa": item["url_directa"],
                "nombre_salida": item["nombre_salida"],
                "query_limpia": query_busqueda,
                "fuente": "Enlace Directo",
            }
            procesada.update({k: item.get(k) for k in ("artista", "titulo", "album", "duration_ms")})
            canciones_procesadas.append(procesada)
            print("  ✓ Enlace directo validado.\n" + "-" * 65)
            continue

        candidatos = buscar_candidatos_multifuente(query_busqueda)
        if not candidatos:
            print(f"  No se encontraron fuentes públicas para '{query_busqueda}'. Omitiendo.\n")
            omitidas += 1
            continue

        opciones_evaluadas = []
        for cand in candidatos[:5]:
            titulo_cand = cand.get("title", "")
            uploader = cand.get("uploader") or cand.get("channel") or "Artista Desconocido"
            url = cand.get("url") or cand.get("webpage_url")
            fuente = "SoundCloud" if url and "soundcloud" in url.lower() else "YouTube"
            score = calcular_similitud(query_busqueda, titulo_cand, uploader)
            opciones_evaluadas.append({
                "url_directa": url,
                "score": score,
                "fuente": fuente,
                "nombre_salida": item["nombre_salida"],
                "query_limpia": query_busqueda,
                "artista": item.get("artista"),
                "titulo": item.get("titulo"),
                "album": item.get("album"),
                "duration_ms": item.get("duration_ms"),
                "titulo_audio": titulo_cand,
                "uploader": uploader,
            })

        opciones_evaluadas.sort(key=lambda x: x["score"], reverse=True)
        if len(opciones_evaluadas) > 1 and opciones_evaluadas[0]["score"] < 85:
            print("  Alerta de similitud. Selecciona la opción correcta:")
            for idx, opc in enumerate(opciones_evaluadas, start=1):
                print(f"     [{idx}] [{opc['fuente']}] {opc['titulo_audio']} | Canal: {opc['uploader']} ({opc['score']:.1f}%)")
            while True:
                try:
                    eleccion = int(input(f"     Selecciona una opción (1-{len(opciones_evaluadas)}): "))
                    if 1 <= eleccion <= len(opciones_evaluadas):
                        seleccionada = opciones_evaluadas[eleccion - 1]
                        break
                except ValueError:
                    pass
                print("     Opción no válida.")
        else:
            seleccionada = opciones_evaluadas[0]
            print(f"  ✓ Coincidencia validada en [{seleccionada['fuente']}]: '{seleccionada['titulo_audio']}' ({seleccionada['score']:.1f}%)")

        canciones_procesadas.append(seleccionada)
        print("-" * 65)

    return canciones_procesadas, omitidas


def descargar_canciones(lista_verificada, calidad_audio):
    print("\nFASE 2: Descarga y conversión a .WAV\n")
    descargadas_ok = 0
    omitidas_existentes = 0
    fallidas = 0

    with tqdm(total=len(lista_verificada), desc="Descargas", unit="canción") as pbar:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS_DESCARGA) as executor:
            futures = [executor.submit(descargar_item, item, calidad_audio) for item in lista_verificada]
            for future in as_completed(futures):
                resultado = future.result()
                if resultado["estado"] == "descargada":
                    descargadas_ok += 1
                elif resultado["estado"] == "omitida_existente":
                    omitidas_existentes += 1
                else:
                    fallidas += 1
                pbar.update(1)
                print(resultado["mensaje"].replace("**", "") + "\n" + "-" * 65)

    return descargadas_ok, omitidas_existentes, fallidas


def previsualizar_y_filtrar(canciones):
    print("\nVista previa de canciones detectadas:")
    for idx, item in enumerate(canciones, start=1):
        artista = item.get("artista") or dividir_artista_titulo(item["nombre_salida"])[0]
        titulo = item.get("titulo") or dividir_artista_titulo(item["nombre_salida"])[1]
        duracion = ""
        if item.get("duration_ms"):
            segundos = int(item["duration_ms"] / 1000)
            duracion = f" [{segundos // 60}:{segundos % 60:02d}]"
        print(f"  [{idx}] {artista} - {titulo}{duracion}")

    entrada = input("\nÍndices a excluir separados por coma, o Enter para descargar todas: ").strip()
    if not entrada:
        return canciones

    excluidas = set()
    for parte in entrada.split(","):
        try:
            excluidas.add(int(parte.strip()))
        except ValueError:
            pass
    return [item for idx, item in enumerate(canciones, start=1) if idx not in excluidas]


def seleccionar_calidad_audio():
    opciones = list(CALIDADES_AUDIO.items())
    print("\nCalidad de audio:")
    for idx, (nombre, _) in enumerate(opciones, start=1):
        print(f"  [{idx}] {nombre}")
    eleccion = input("Selecciona una opción (1-2, Enter = 2): ").strip() or "2"
    try:
        return opciones[int(eleccion) - 1][0]
    except (ValueError, IndexError):
        return opciones[1][0]


def mostrar_menu():
    print("+" * 60)
    print("      WELCOME TO AMATEUR DJ AGENT (ADA) - MUSIC DOWNLOADER")
    print("+" * 60)
    print("\n ¿Desde dónde descargarás?")
    print("  [1] Playlist de Spotify (URL pública)")
    print("  [2] Playlist de YouTube (URL pública / no listada)")
    print("  [3] Playlist de SoundCloud (URL pública / no listada)")
    print("  [4] Una sola canción (SoundCloud / YouTube / Bandcamp)")
    print("  [5] Ninguna, salir.\n")


def main():
    while True:
        mostrar_menu()
        opcion = input("Selecciona una opción (1-5): ").strip()
        canciones_obtenidas = []

        if opcion == "1":
            url_input = input("\n> Ingresa la URL de la Playlist de Spotify: ").strip()
            if url_input:
                canciones_obtenidas = obtener_metadatos_spotify(url_input)
        elif opcion == "2":
            url_input = input("\n> Ingresa la URL de la Playlist de YouTube: ").strip()
            if url_input:
                canciones_obtenidas = obtener_metadatos_ytdlp(url_input, "YouTube")
        elif opcion == "3":
            url_input = input("\n> Ingresa la URL de la Playlist de SoundCloud: ").strip()
            if url_input:
                canciones_obtenidas = obtener_metadatos_ytdlp(url_input, "SoundCloud")
        elif opcion == "4":
            url_input = input("\n> Ingresa la URL de la canción (SoundCloud / YouTube / Bandcamp): ").strip()
            if url_input:
                canciones_obtenidas = obtener_metadatos_cancion_unica(url_input)
        elif opcion == "5":
            print("\nSaliendo del agente... ¡Buenas mezclas, DJ!")
            break
        else:
            print("Esa opción no es válida. Intenta nuevamente.\n")
            continue

        if not canciones_obtenidas:
            print("No se identificaron canciones.\n")
            continue

        total_detectadas = len(canciones_obtenidas)
        canciones_seleccionadas = previsualizar_y_filtrar(canciones_obtenidas)
        if not canciones_seleccionadas:
            print("No se seleccionaron canciones para descargar.\n")
            continue

        nombre_calidad = seleccionar_calidad_audio()
        print(f"\nCalidad seleccionada: {nombre_calidad}\n")
        canciones_verificadas, total_omitidas = analizar_y_resolver_coincidencias(canciones_seleccionadas)

        total_exito = 0
        total_existentes = 0
        total_fallidas = 0
        if canciones_verificadas:
            total_exito, total_existentes, total_fallidas = descargar_canciones(canciones_verificadas, nombre_calidad)

        print("+" * 60)
        print("        RESUMEN FINAL DEL PROCESO")
        print("+" * 60)
        print(f"\n  Canciones detectadas:              {total_detectadas}")
        print(f"  Canciones seleccionadas:           {len(canciones_seleccionadas)}")
        print(f"  Descargadas con éxito (.WAV):      {total_exito}")
        print(f"  Omitidas porque ya existían:       {total_existentes}")
        print(f"  Omitidas (sin fuentes libres):     {total_omitidas}")
        print(f"  Fallidas (errores de descarga):    {total_fallidas}")
        print("+" * 60)


if __name__ == "__main__":
    main()
