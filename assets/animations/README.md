# Loaders visuales

Guarda aqui los loaders de la app.

## Archivo esperado por defecto

```text
assets/animations/loading_dj.gif
```

## Dimensiones recomendadas

- Loader pequeno dentro del formulario: `220x220 px`.
- Loader mediano centrado: `320x320 px`.
- Loader horizontal tipo waveform/equalizer: `480x160 px`.

Para la app actual, usa preferentemente `220x220 px` o `320x320 px`.

## Formatos

- `.gif`: opcion mas simple para Streamlit.
- `.webp`: buena calidad y peso bajo si es animado.
- `.mp4`: mejor para animaciones mas largas o cinematicas.

## Peso recomendado

Mantener cada loader bajo `2 MB` si es posible. Idealmente entre `300 KB` y `1.5 MB`.

## Varios loaders

Puedes guardar varios archivos, por ejemplo:

```text
loading_dj.gif
loading_equalizer.gif
loading_waveform.gif
```

En `app.py` hay un comentario junto a `LOADING_ANIMATION` para activar seleccion aleatoria.
