# Despliegue

## El aplicativo en Streamlit Community Cloud

El repositorio es **autocontenido**: `data/travel_analitica.sqlite` viaja en él
y el aplicativo construye el DuckDB en memoria al arrancar. No hay base que
descargar, ni credenciales, ni servicios externos que configurar.

### Pasos

1. Entrar en <https://share.streamlit.io> con la cuenta de GitHub.
2. **New app** → repositorio
   `Olivertc24/Analisis-Concentracion-del-Retraso-en-la-Red-Aerea-Domestica-2017`,
   rama `main`, archivo principal `app.py`.
3. Elegir la URL. Propuesta: `retraso-red-aerea-2017`.
4. **Deploy**.

No hay que tocar la sección de *Secrets*: el aplicativo no usa ninguno.

### Qué esperar

La primera construcción instala las cuatro dependencias de
[`requirements.txt`](requirements.txt) y tarda unos minutos. Después, cada
arranque carga la base en memoria en unos 65 ms.

---

## Tres fallos conocidos de Streamlit Cloud

Los tres aparecieron en despliegues anteriores de esta misma serie de trabajos.
Ninguno se manifiesta en local.

### 1. El vigilante de archivos agota el límite del sistema

El contenedor tiene un tope bajo de *inotify watches*. El vigilante de
Streamlit lo agota y llena la bitácora de errores hasta hacerla ilegible.

**Ya está resuelto** en [`.streamlit/config.toml`](.streamlit/config.toml) con
`fileWatcherType = "none"`. En producción no hay nada que vigilar, porque el
código no cambia mientras la aplicación corre.

### 2. DuckDB reserva memoria del anfitrión, no del contenedor

DuckDB toma por defecto el 80 % de la memoria **de la máquina**, no la del
contenedor, y el proceso muere sin dejar un error claro.

**Aquí no debería ocurrir**, porque la base entera son 5 MB y cabe de sobra.
Si llegara a pasar, se arregla añadiendo en `src/query_manager.py`, justo
después de abrir la conexión:

```python
con.execute("SET memory_limit='512MB'")
con.execute("SET threads=2")
```

### 3. La plataforma degrada una dependencia después de arrancar

En un despliegue anterior, la plataforma detectó una versión de `pyarrow` que
consideraba problemática y la sustituyó **después** de que el proceso ya
estuviera en marcha. El resultado fue que las consultas empezaron a devolver
`None` y la aplicación falló con un `AttributeError` que no decía nada.

**Se arregla reiniciando la aplicación** —*Manage app* → ⋮ → *Reboot app*—,
no volviendo a desplegar. El síntoma es una traza incomprensible justo después
de un primer despliegue aparentemente correcto; en la bitácora de la
plataforma se ve la línea que sustituye el paquete.

---

## El tablero en Tableau Public

Los extractos se generan con
[`Tableau/generar_extractos.py`](Tableau/generar_extractos.py) y el libro se
construye en Tableau Desktop. Ver [`Tableau/README.md`](Tableau/README.md).

**Tableau Public no se conecta a fuentes en vivo**: sólo publica extractos. El
tablero no consulta la base del aplicativo, lleva sus propios datos dentro.

### Al publicar

Tres gestos rompen Tableau sin dar ningún error, y los tres se aprendieron a
base de perder trabajo:

- **No cerrar un libro.** Al cerrarlo, Tableau abre un `Libro1` vacío que se
  queda con el foco y desactiva la opción de publicar.
- **No usar el diálogo *Archivo → Abrir*.** Deja una ventana fantasma que
  retiene el foco y no se puede cerrar.
- **Verificar el nombre que propone el diálogo antes de guardar.** Si propone
  el de otro libro, el documento activo no es el que se cree: hay que cancelar.

El procedimiento que funciona es **un libro por sesión de Tableau**: abrir sólo
ese `.twbx`, publicarlo y salir.
