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
- `data/review.md`: resumen de la programación, frecuencia observada, series por músculo principal y campos faltantes de D. Incluye contexto para preparar una propuesta de mejora con los datos reales.

Los archivos contienen información personal y se excluyen de Git. Cada ejecución reemplaza la descarga anterior. El comando realiza una sincronización manual.

## Entrenamientos nuevos mediante webhook

En [cloudflare/README.md](cloudflare/README.md) está preparado un receptor para **Cloudflare Workers Free + D1 Free**, pensado para funcionar aunque la computadora esté apagada. Recibe y guarda únicamente los entrenamientos nuevos desde que se active la suscripción en Hevy; no sube rutinas, historial anterior ni archivos locales.

El receptor está desplegado en Workers Free y suscrito en Hevy. Guarda el aviso antes del 200, consulta el entrenamiento por ID en segundo plano y recupera pendientes con un cron. El recorrido completo se verificó con un entrenamiento nuevo de prueba creado por el usuario, sin importar historial. No incluye análisis de IA de pago ni envíos de notificaciones.

Para otra ventana de historial:

```sh
python3 -m fitness_agent sync --weeks 8
```

La descarga consulta todas las páginas del historial para filtrar por fecha sin depender del orden del servidor. Solo guarda las sesiones de las rutinas seleccionadas dentro de la ventana.

## Criterios de revisión

La selección de rutinas exige el nombre completo; tolera mayúsculas, espacios, variantes de guiones y adornos emoji. Si falta alguna o hay nombres duplicados, informa el problema antes de generar archivos. Se puede ajustar la lista `ACTIVE_ROUTINES` en `fitness_agent/hevy.py` si cambian los nombres.

Las sesiones se vinculan por `routine_id`. Cuando falta ese campo, se acepta el título exacto como asociación provisional y se marca para revisión. Estas asociaciones por título no se incluyen en el volumen por músculo. Los calentamientos se excluyen del conteo de trabajo. Las series se atribuyen solo al músculo principal de Hevy; no se estima trabajo indirecto ni se comparan como equivalentes distintos tipos de series.

El informe es descriptivo: no diagnostica estancamiento, no inventa cargas y no genera automáticamente una rutina mejorada por IA. Para una propuesta personalizada de D se revisan los datos descargados y se completan días disponibles, orden semanal, tiempo por sesión, equipo y limitaciones.

El cliente Python implementado solo hace consultas `GET`. Los cambios ya aplicados a D se realizaron mediante operaciones puntuales autorizadas y verificadas; todavía no hay un comando de escritura en el CLI. La API key también puede permitir cambios en Hevy: mantenela local y privada. Documentación oficial: <https://api.hevyapp.com/docs/>.

## Verificación

```sh
python3 -m unittest discover -s tests -v
```

Las pruebas cubren paginación, autenticación sin exposición de claves, reintentos, selección de rutinas, fechas, asociaciones ambiguas, exclusión de calentamientos y el flujo de descarga con respuestas simuladas. Para verificar acceso real a tu cuenta hace falta configurar la credencial.
