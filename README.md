# fitness-ai-agent

Integración local con la API oficial de Hevy para obtener estas rutinas actuales:

- **B - Lower**
- **D - I Am The Shadows**
- **E - Redemption (Now or Never)**

Objetivo: **hipertrofia**. Primera prioridad: revisar y mejorar **D** considerando B y E.

## Documentación

La [documentación del proyecto](docs/README.md) reúne preferencias, arquitectura con diagramas y operación. Los [pendientes](docs/backlog.md) indican qué falta comprobar o implementar.

## Conectar tu cuenta

Requiere Python 3.10 o posterior y Hevy Pro. No hay dependencias que instalar.

1. Generá una API key en <https://hevy.com/settings?developer>.
2. Desde la terminal de este proyecto, ejecutá:

   ```sh
   python3 -m fitness_agent setup
   ```

3. Pegá la clave en el campo oculto. Se valida con Hevy y se guarda en `.env` con permisos `600`, excluido de Git. No la pegues en el chat.
4. Descargá las rutinas y el historial:

   ```sh
   python3 -m fitness_agent sync
   ```

También podés configurar `HEVY_API_KEY` en el entorno o copiar `.env.example` a `.env`. La variable de entorno tiene prioridad.

## Resultado

- `data/snapshot.json`: las tres rutinas completas, las sesiones asociadas de las últimas 12 semanas y el catálogo de los ejercicios usados. Conserva las notas, series, pesos, repeticiones, RPE, descansos y superseries que Hevy entrega.
- `data/review.md`: resumen de la programación, frecuencia observada, series por músculo principal y campos faltantes de D. Aplica `data/preferences.json` si existe: separa series previstas de las guardadas solo como referencia (omisiones), y señala descansos u orden de D distintos de lo acordado. Compara las dos últimas sesiones de D por ejercicio: cargas en kg y lb, repeticiones a igual carga, series fuera del rango previsto y cambios de condiciones.

Un `preferences.json` inválido detiene `sync` antes de consultar Hevy y conserva la descarga anterior.

Los archivos contienen información personal y se excluyen de Git. Cada ejecución reemplaza la descarga anterior. El comando realiza una sincronización manual.

## Entrenamientos nuevos mediante webhook

En [cloudflare/README.md](cloudflare/README.md) está preparado un receptor para **Cloudflare Workers Free + D1 Free**, pensado para funcionar aunque la computadora esté apagada. Recibe y guarda únicamente los entrenamientos nuevos desde que se active la suscripción en Hevy; no sube rutinas, historial anterior ni archivos locales.

El receptor está desplegado en Workers Free y suscrito en Hevy. Guarda el aviso antes del 200, consulta el entrenamiento por ID en segundo plano y recupera pendientes con un cron. El recorrido completo se verificó con un entrenamiento nuevo de prueba creado por el usuario, sin importar historial. No incluye análisis de IA de pago ni envíos de notificaciones.

Para descargar los entrenamientos que recibió el webhook:

```sh
python3 -m fitness_agent pull
```

Lee `READ_API_AUTH` del entorno o de `data/cloudflare-private.json`. Agrega los entrenamientos a `data/cloud-workouts.json` por ID y guarda el cursor en `data/cloud-cursor.json` solo después de escribirlos; si se interrumpe, la siguiente ejecución repite la página sin duplicar. `CLOUD_API_URL` permite usar otro Worker.

## Reporte por entrenamiento

```sh
python3 -m fitness_agent report                 # descarga lo recibido por el webhook y reporta lo nuevo
python3 -m fitness_agent report --workout <ID>  # un entrenamiento concreto de Hevy, de cualquier rutina
```

Genera `data/reports/<id>.md` y `.json` con la estructura de [docs/draft.md](docs/draft.md): lectura, análisis por ejercicio, trabajo para hipertrofia, contexto reciente, próximas acciones y datos faltantes. Compara cada ejercicio con su sesión anterior en todo el historial de Hevy, separa calentamientos, respeta las omisiones y marca condiciones que invalidan la comparación. Las cifras se calculan con código; las secciones de interpretación quedan marcadas como pendientes porque todavía no se eligió modelo ni presupuesto. No llama a servicios de IA.

Cada reporte guarda la versión del análisis y una huella del entrenamiento: repetir el comando no lo duplica, y se regenera solo si Hevy muestra una edición o cambia la versión. `--force` lo regenera igualmente. Si un entrenamiento recibido ya no está en Hevy, el reporte lo indica.

## Cambiar una rutina con respaldo

```sh
python3 -m fitness_agent routine export "D - I Am The Shadows"
# editar data/routines/<id>.json
python3 -m fitness_agent routine apply data/routines/<id>.json            # simulación: muestra diferencias
python3 -m fitness_agent routine apply data/routines/<id>.json --confirm  # aplica en Hevy
```

`apply` valida el archivo y comprueba que la rutina siga en la versión exportada; terminar un entrenamiento también la actualiza, así que conviene exportar justo antes de editar. Con `--confirm` guarda el estado anterior en `data/changes/`, escribe con `PUT /v1/routines/{id}` y vuelve a leer la rutina para verificar el resultado. Es la única escritura del proyecto.

## Espacio del gimnasio (3D)

```sh
python3 -m fitness_agent gym space   # abre el plano 3D en el navegador para ubicar las máquinas
```

Abre en `127.0.0.1` una página para ubicar las máquinas sobre el plano del gimnasio. La lista ofrece todas las máquinas del catálogo de Hevy agrupadas por máquina física (40 modelos: prensa, polea, pec deck, jalón, Smith, mancuernas…), cada una con su modelo 3D y los ejercicios de Hevy que se hacen en ella. Al agregar una máquina se arrastra sobre el piso, se gira con `R` y se elige qué ejercicios admite. Las estaciones de tus rutinas que aún no están en el plano aparecen aparte, y al ubicarlas se unen las que usan la misma máquina. Guarda en `data/gyms.json` con validación, un respaldo por sesión en `data/changes/` y rechazo si el archivo cambió fuera de la página.

El modo **Plano: salas y puertas** se usa como un juego de pintar, sin dibujar líneas ni vértices:

1. **Salas:** en el panel se elige una sala o se crea con **+ Nueva sala** (peso libre, cardio, vestuario…) y se le escribe el nombre.
2. **Pintar:** con 🖌️ Pintar o ▭ Rectángulo se pintan sus casillas sobre la cuadrícula; cada casilla es 1 m × 1 m. Con 🧽 Borrar se quitan las casillas que no son del gimnasio, así un local en L u otra forma queda con su contorno real. **Tamaño del terreno** fija el rectángulo donde se pinta.
3. **Puertas:** con 🚪 Puertas se toca la pared (línea oscura) entre dos salas para abrir o cerrar una puerta de 1 m; tocando la pared de al lado se hace más ancha.

Las paredes aparecen solas entre salas distintas. Una sala sin la casilla **Paredes** es solo una zona marcada dentro de un salón abierto y se camina libre hacia sus vecinas. ⌘/Ctrl+Z deshace y ⇧⌘/Ctrl+Shift+Z rehace.

Del plano pintado (`layout.grid`) sale lo que usan el grafo y `gym path`: el contorno, una sección por sala y las paredes entre salas con sus puertas. Cada máquina muestra su sección, y las que quedan fuera del contorno o encima de un muro se marcan para revisar. Si el plano todavía no sirve (partes separadas, o dos partes que se tocan solo por una esquina), la página dice qué corregir y no lo guarda.

Hevy no ofrece modelos 3D: los modelos se dibujan con three.js a partir de la clasificación de `fitness_agent/machines.py`. La página necesita internet para cargar la librería; los datos no salen del equipo. El catálogo se descarga la primera vez en `data/exercise-catalog.json` y se actualiza con `gym catalog`.

## Grafo de cercanía

```sh
python3 -m fitness_agent gym graph   # distancias entre máquinas ubicadas y orden propuesto por rutina
```

Es una función aparte del espacio 3D. Con las posiciones guardadas, une las estaciones a 6 m o menos caminando (`settings.near_meters` de cada gimnasio). Si el gimnasio tiene forma dibujada, la distancia es el camino más corto dentro del contorno, rodeando paredes y pasando por las puertas (`fitness_agent/layout.py`); sin forma, es la línea recta. Las máquinas fuera del contorno no entran en el grafo, dos salas sin puerta entre sí quedan desconectadas y el informe lista qué máquinas hay en cada sección. Informa los grupos cercanos y calcula los metros recorridos por B, D y E. Para B y E propone un orden que adelanta las máquinas más ocupadas y reduce el recorrido sin alejarse del orden actual. D conserva el orden acordado. La ocupación habitual se anota por estación en `busy` (0 a 3). El detalle queda en `data/gym-graph.json`; las propuestas no cambian Hevy.

## Recorrido 3D

```sh
python3 -m fitness_agent gym path   # abre en el navegador el recorrido de cada rutina sobre las máquinas
```

Es otra página, separada de `gym space` y de solo lectura (puerto 8766 por defecto, así pueden estar abiertas a la vez). Muestra las máquinas ubicadas con sus modelos 3D, el grafo de cercanía en el piso y, por rutina, el camino como arcos luminosos numerados del primer al último ejercicio. El anillo de cada máquina indica su ocupación habitual.

Estar al lado no es estar cerca: con la forma dibujada, cada tramo de la rutina y cada unión del grafo siguen el camino caminando por las puertas en vez de atravesar paredes. Las máquinas pegadas a ambos lados de una pared se unen con guiones rojos y se listan en **Al lado, pero separadas por pared**, con los metros en línea recta y caminando (o «sin camino» si no hay puerta). No cuentan como cercanas ni para el orden propuesto. Sin forma dibujada, la página avisa que las distancias son en línea recta y no saben de paredes.

- **Actual / Propuesta / Comparar:** el orden de la rutina, el que propone `gym graph` o ambos superpuestos, con los metros de cada uno y en qué lugar estaba antes cada ejercicio.
- **Recorrer:** una luz va de máquina en máquina con la cámara siguiéndola; las flechas avanzan paso a paso y un clic en un paso o en una máquina la enfoca.
- **Recargar:** vuelve a leer `data/gyms.json` después de guardar cambios en `gym space`.

Los cálculos son los de `gym graph`; la página no guarda nada. `#routine=e&mode=compare&view=top` en la URL abre directamente una rutina, un modo y la vista superior.

`gym init` crea `data/gyms.json` desde las rutinas y `gym check` lo valida y cuenta los cambios de zona.

## Otra ventana de historial

Para descargar otra cantidad de semanas con `sync`:

```sh
python3 -m fitness_agent sync --weeks 8
```

La descarga consulta todas las páginas del historial para filtrar por fecha sin depender del orden del servidor. Solo guarda las sesiones de las rutinas seleccionadas dentro de la ventana.

## Criterios de revisión

La selección de rutinas exige el nombre completo; tolera mayúsculas, espacios, variantes de guiones y adornos emoji. Si falta alguna o hay nombres duplicados, informa el problema antes de generar archivos. Se puede ajustar la lista `ACTIVE_ROUTINES` en `fitness_agent/hevy.py` si cambian los nombres.

Las sesiones se vinculan por `routine_id`. Cuando falta ese campo, se acepta el título exacto como asociación provisional y se marca para revisión. Estas asociaciones por título no se incluyen en el volumen por músculo. Los calentamientos se excluyen del conteo de trabajo. Las series se atribuyen solo al músculo principal de Hevy; no se estima trabajo indirecto ni se comparan como equivalentes distintos tipos de series.

El informe es descriptivo: no diagnostica estancamiento, no inventa cargas y no genera automáticamente una rutina mejorada por IA. Para una propuesta personalizada de D se revisan los datos descargados y se completan días disponibles, orden semanal, tiempo por sesión, equipo y limitaciones.

El cliente Python hace consultas `GET` y una única escritura, `routine apply --confirm`, con verificación de versión, respaldo y relectura. La API key también puede permitir cambios en Hevy: mantenela local y privada. Documentación oficial: <https://api.hevyapp.com/docs/>.

## Verificación

```sh
python3 -m unittest discover -s tests -v
```

Las pruebas cubren paginación, autenticación sin exposición de claves, reintentos, selección de rutinas, fechas, asociaciones ambiguas, exclusión de calentamientos, preferencias, descarga desde Cloudflare, reportes, cambios de rutina, inventario, clasificación de máquinas, espacio 3D y grafo de cercanía, con respuestas simuladas. Para verificar acceso real a tu cuenta hace falta configurar la credencial.
