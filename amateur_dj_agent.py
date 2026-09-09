"""Compatibilidad: ejecuta la interfaz de consola de ADA.

La lógica compartida vive en ada_core.py y la CLI principal vive en ada.py.
"""

from ada import main


if __name__ == "__main__":
    main()
