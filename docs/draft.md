# Borrador de posibles agentes

Documento de exploración. Registra candidatos y sus responsabilidades antes de elegir herramientas o implementar. Las propuestas técnicas y el formato del reporte siguen abiertos; este archivo no cambia el comportamiento actual del proyecto.

## 1. Analista de entrenamientos para hipertrofia

### Propósito

Generar un reporte profundo por cada entrenamiento completado en Hevy, con el criterio de un entrenador personal enfocado en hipertrofia. Interpretar la sesión dentro del historial, la rutina y las preferencias del usuario, y proponer qué hacer a continuación con argumentos verificables.

Es el primer candidato de un futuro conjunto de agentes. Su responsabilidad es el análisis posterior a cada entrenamiento; el segundo candidato planifica el desarrollo del entrenamiento a lo largo del tiempo. Tener varios agentes en el producto no exige que todos intervengan en cada reporte.

### Lo acordado

- Cada entrenamiento debe tener su propio reporte, sin necesidad de solicitarlo manualmente.
- El reporte tendrá una estructura definida y ofrecerá análisis profundo, además de describir resultados.
- El foco es entrenamiento e hipertrofia, con recomendaciones contextualizadas.
- La experiencia deseada es recibir una notificación y consultar el reporte en una app en la nube.
- Telegram queda como posible canal inicial, sin una decisión tomada. WhatsApp no es la primera opción por la preocupación del usuario respecto al costo.
- El correo mediante Gmail API queda como otra alternativa, pendiente de comparar con Telegram y las notificaciones de la app.
- Conversar con el agente para agregar contexto podría ser una ampliación posterior. No es un requisito de la primera versión.

### Entradas propuestas

- **Sesión completada:** ejercicios, orden, series, cargas, repeticiones, tipos de serie, duración, notas y esfuerzo registrado cuando estén disponibles.
- **Historial comparable:** sesiones anteriores y trabajo reciente para interpretar tendencias y contexto semanal. La ventana de comparación queda por definir.
- **Rutina prevista:** ejercicios, rangos, series, descansos y omisiones intencionales, si existe una rutina asociada.
- **Perfil y preferencias:** objetivo, frecuencia habitual, restricciones y decisiones ya acordadas. La fuente de preferencias está en [Preferencias de entrenamiento](business/training-preferences.md).
- **Contexto opcional:** observaciones que el usuario ya haya registrado. Sueño, molestias o disponibilidad de equipo no deben darse por conocidos.

La falta de historial, rutina o esfuerzo registrado no impide emitir un reporte: reduce las conclusiones posibles y debe quedar visible.

### Estructura propuesta del reporte

La estructura será consistente entre entrenamientos. Este es un primer borrador para acordar el contenido antes de implementar.

1. **Lectura de la sesión.** Conclusiones principales, qué salió bien y qué merece atención.
2. **Análisis por ejercicio.** Trabajo realizado, comparación con sesiones equivalentes y evolución de cargas, repeticiones y esfuerzo. Explicar cuándo una comparación deja de ser válida por cambios de ejercicio, máquina, tipo de serie u otras condiciones conocidas.
3. **Trabajo para hipertrofia.** Distribución de series de trabajo, rangos de repeticiones y esfuerzo disponible, cumplimiento de lo previsto y caída de rendimiento entre series. Separar observaciones de interpretaciones y evitar equiparar tonelaje con estímulo o crecimiento muscular.
4. **Contexto reciente.** Cómo encaja la sesión en el trabajo semanal y las tendencias observadas. Diferenciar una variación aislada de un patrón repetido y no atribuir automáticamente una caída de rendimiento a fatiga o mala recuperación.
5. **Próximas acciones.** Qué mantener, dónde considerar progresar y qué observar antes de ajustar. Cada propuesta debe indicar los datos que la sustentan y las condiciones necesarias para aplicarla. Mantener lo actual también es una conclusión válida.
6. **Datos faltantes y límites.** Qué no se pudo evaluar, qué se asumió y qué información mejoraría el siguiente análisis.

El análisis puede ser extenso; la notificación debe ser breve y llevar al reporte completo. No se define todavía una puntuación global ni un objetivo de longitud.

### Criterios del análisis

- Los cálculos de series, repeticiones, cargas y comparaciones se obtienen mediante código verificable; el modelo interpreta esos resultados.
- Separar calentamientos de series de trabajo y series realizadas de series guardadas únicamente como referencia. Respetar las omisiones intencionales del usuario.
- No sumar tipos de series o ejercicios distintos como si fueran equivalentes. Explicitar el criterio utilizado para atribuir trabajo a músculos y cualquier estimación de trabajo indirecto.
- Cada conclusión debe poder vincularse a la sesión, al historial, a una preferencia o a una referencia de entrenamiento identificable. Una hipótesis debe presentarse como tal.
- No inventar esfuerzo, descansos reales, técnica, dolor ni recuperación. Distinguir los valores programados de los efectivamente registrados.
- No afirmar crecimiento muscular medido, calidad técnica o proximidad al fallo cuando los datos no lo permiten.
- Los principios de entrenamiento utilizados deberán apoyarse en referencias revisadas y mantenerse separados de las observaciones personales.
- Emitir recomendaciones para revisión; modificar rutinas en Hevy no forma parte de este agente en la primera versión.

### Flujo propuesto

1. El flujo existente recibe el aviso, obtiene el detalle y deja el entrenamiento nuevo guardado como procesado.
2. Un proceso separado prepara el contexto y calcula las métricas. La generación del reporte no bloquea la respuesta del webhook.
3. El agente genera el reporte con la estructura acordada y se validan sus datos y formato.
4. El reporte se guarda asociado al ID del entrenamiento, con fecha de generación y versión del análisis.
5. Se envía una notificación con un breve adelanto y acceso al reporte completo.

La recepción repetida de un mismo evento no debe duplicar reportes ni notificaciones. Los fallos de generación y entrega deben poder reintentarse por separado. El tratamiento de entrenamientos editados o eliminados, así como las regeneraciones del reporte, queda pendiente de definición.

### Entrega y consulta

- **Destino deseado:** app en la nube con acceso privado e historial de reportes por entrenamiento.
- **Notificación:** aviso de que el reporte está listo, con una síntesis breve y enlace. El mecanismo de notificaciones de la app queda por elegir.
- **Canal inicial posible:** Telegram para avisos y acceso al reporte. La generación y el almacenamiento del análisis deben ser independientes del canal.
- **Alternativa por correo:** Gmail API para enviar una síntesis y el enlace al reporte privado; queda por decidir si también se incluirá el reporte completo en el correo. Requiere configurar la autorización de Google y el envío desde la cuenta elegida.
- **Costo del correo:** la documentación de Google indica que el uso estándar de Gmail API no tiene costo adicional y está sujeto a cuotas. Antes de implementarlo, comprobar las condiciones aplicables al proyecto y los límites de envío de la cuenta. La generación del análisis con IA tiene un presupuesto separado. Referencia: [cuotas y precios de Gmail API](https://developers.google.com/workspace/gmail/api/reference/quota).
- **Ampliación posible:** permitir respuestas del usuario que añadan contexto y, si corresponde, producir una revisión identificable del reporte.

### Qué falta frente al sistema actual

La [arquitectura actual](architecture/overview.md) ya recibe y guarda entrenamientos nuevos en Cloudflare. `python3 -m fitness_agent report` genera localmente la parte calculada de este reporte, con su estructura, versión e idempotencia; las secciones de interpretación quedan pendientes del modelo. Todavía no envía notificaciones.

La nube no dispone del historial anterior, las rutinas ni las preferencias locales. Debe definirse qué contexto se incorporará, cómo se actualizará y dónde se ejecutará el análisis.

La cobertura buscada es cada entrenamiento completado, incluso si no pertenece a B, D o E. El CLI actual limita su descarga a esas rutinas; esa selección no debe convertirse por accidente en el alcance de este agente. El alcance temporal de la primera versión y cualquier procesamiento retroactivo quedan por acordar.

### Criterios de aceptación propuestos

- Un entrenamiento nuevo procesado produce un reporte persistido con la estructura acordada y vinculado a su ID.
- Un entrenamiento sin historial comparable también recibe reporte y muestra esa limitación.
- Las cifras del reporte coinciden con los datos y los cálculos disponibles; las recomendaciones explican su fundamento.
- Las preferencias y omisiones intencionales se respetan en las comparaciones.
- Un evento repetido no produce otra notificación ni otro reporte equivalente.
- Si falla el análisis o la entrega, el entrenamiento permanece guardado y se puede reintentar la etapa pendiente.
- El usuario puede consultar reportes anteriores desde el destino elegido.

### Decisiones pendientes

- Acordar la plantilla final y el nivel de detalle del reporte.
- Elegir historial y preferencias necesarios, su sincronización y el criterio para comparar sesiones.
- Definir las referencias de entrenamiento y cómo evaluar la utilidad y consistencia del análisis con sesiones reales.
- Elegir modelo, entorno de ejecución y presupuesto por reporte; no se presupone que la inferencia sea gratuita.
- Elegir app y notificaciones desde el inicio, Telegram o correo mediante Gmail API como primera entrega.
- Resolver retención, ediciones, eliminaciones, reintentos y regeneraciones.
- Evaluar si hace falta un framework de orquestación. LangGraph y CrewAI son opciones por estudiar, no decisiones tomadas.

## 2. Planificador del entrenamiento basado en evidencia

### Propósito

Planificar el desarrollo del entrenamiento para hipertrofia a lo largo del tiempo: objetivos de largo plazo, mesociclos y microciclos. Convertir el historial, las preferencias y los resultados observados en una estrategia que pueda revisarse con el usuario y que el tercer agente traduzca en ajustes concretos de sus rutinas.

El enfoque buscado es **entrenamiento basado en evidencia** (*science-based training* o *evidence-based training*), en la línea de divulgación de [Jeff Nippard](https://jeffnippard.com/). Es una referencia del enfoque deseado; las decisiones deben contrastarse con investigación identificable y con la respuesta individual del usuario.

### Responsabilidades propuestas

- Definir objetivos y prioridades por bloque y cómo evaluar su evolución con los datos disponibles.
- Proponer mesociclos con objetivos, duración revisable y criterios para mantener, ajustar o cerrar el bloque.
- Organizar microciclos según los días disponibles, la distribución de rutinas y las prioridades musculares.
- Definir prioridades, distribución del trabajo y criterios de progresión que orienten los ejercicios, series y demás detalles propuestos por el tercer agente.
- Investigar las preguntas de entrenamiento necesarias para el plan y registrar las fuentes, sus limitaciones y las condiciones en las que se pueden aplicar. Ese conocimiento también estará disponible para el tercer agente.
- Evaluar cuándo conviene mantener el plan, modificar el trabajo o proponer una descarga, explicando el fundamento y los datos faltantes.
- Adaptar el plan a cambios de disponibilidad, equipo, preferencias y resultados, conservando las decisiones ya acordadas.
- Considerar el gimnasio previsto para cada sesión y su inventario confirmado al distribuir las rutinas del bloque.

### Entradas y relación con el primer agente

- Objetivo, experiencia, días disponibles, tiempo por sesión, equipo, preferencias y limitaciones confirmadas por el usuario.
- Rutinas actuales e historial de sesiones, vinculados por ID cuando exista. Los nombres pueden cambiar sin definir una rutina nueva.
- Reportes del primer agente y datos que los sustentan, además del seguimiento del plan y el contexto comunicado por el usuario.

El primer agente analiza lo realizado; el segundo organiza los bloques y sus objetivos; el tercero optimiza las rutinas actuales dentro de ese marco. Una sesión aislada no debe provocar automáticamente una reestructuración del plan. Se deben definir revisiones periódicas y situaciones que justifiquen revisar antes.

### Entregable propuesto

Un plan versionado con objetivo del bloque, distribución de microciclos, rutinas previstas, criterios de progresión, puntos de revisión y razones de cada cambio. Debe distinguir lo propuesto, lo aprobado y lo realizado, y conservar el vínculo con versiones anteriores.

Las propuestas se revisan con el usuario antes de modificar rutinas en Hevy. El mecanismo para aplicar cambios queda por definir.

### Criterios y decisiones pendientes

- Apoyar las recomendaciones en investigación identificable, priorizando revisiones y estudios pertinentes; diferenciar evidencia, interpretación y preferencias personales.
- Explicar cómo se adapta cada principio al usuario, sin asumir que una estructura de periodización es superior para todos ni fijar cifras universales antes de revisar el contexto.
- No inferir recuperación, dolor o proximidad al fallo si no están registrados; solicitar el contexto que cambie una decisión.
- Definir el contexto inicial necesario, la estructura del plan y la frecuencia de revisión.
- Acordar las fuentes de entrenamiento, su actualización y cómo se resolverán recomendaciones contradictorias.
- Definir cómo recibe los reportes del primer agente y cómo se conservan las aprobaciones y versiones del plan.

## 3. Optimizador de rutinas actuales

### Propósito

Revisar y mejorar las rutinas que el usuario ya utiliza, aprovechando el análisis de sus sesiones y la investigación y planificación del segundo agente. Proponer cambios concretos y justificados que respeten sus preferencias, equipo, tiempo disponible y objetivos del bloque.

### Entradas y responsabilidades propuestas

- Leer la versión actual de la rutina, sus sesiones comparables, los reportes del primer agente y el plan y las referencias del segundo.
- Revisar selección y orden de ejercicios, series, rangos, descansos, objetivos de esfuerzo, progresión y sustituciones.
- Considerar cada rutina dentro de la distribución semanal para detectar redundancias o necesidades de ajuste, sin evaluar B, D o E de forma aislada.
- Respetar las restricciones del usuario, como el orden por disponibilidad de máquinas y los ejercicios omitidos intencionalmente.
- Utilizar el inventario y el mapa del gimnasio elegido para proponer ejercicios realizables y agrupar estaciones cercanas, reduciendo desplazamientos y cambios de zona. Conservar las prioridades de entrenamiento y explicar cualquier compromiso entre orden y recorrido.
- Consultar al planificador si un cambio propuesto altera los objetivos o la distribución del bloque. Registrar cualquier discrepancia pendiente.
- Poder recomendar mantener la rutina cuando no haya motivos suficientes para cambiarla.

### Entregable y aplicación

Una propuesta que muestre la rutina actual y la propuesta, detalle cada cambio, explique su motivo y vincule los datos personales y las referencias utilizados. Debe indicar qué resultado se espera observar y cuándo revisar si el cambio fue útil.

La aplicación en Hevy requiere aprobación del usuario. Antes de escribir, comprobar que la rutina sigue en la versión revisada; después, volver a leerla y verificar el resultado. Conservar versiones para relacionar las sesiones posteriores con el plan aprobado. La identificación debe hacerse por ID, aunque cambie el nombre.

Quedan por definir la plantilla de comparación y el mecanismo de aprobación. Para aplicar y revertir ya existe `routine apply`, con verificación de versión, respaldo y relectura; el optimizador no lo ejecuta por su cuenta.

## 4. Seguimiento de contexto y recuperación

### Propósito

Recoger mediante consultas breves el contexto que Hevy no registra: descanso percibido, esfuerzo, molestias, disponibilidad y motivos para omitir o sustituir ejercicios. El usuario considera este cuarto agente parte del ecosistema propuesto; quedan por definir su alcance inicial y su implementación.

### Responsabilidades propuestas

- Registrar lo comunicado por el usuario y cuándo aplica, evitando repetir preguntas ya contestadas.
- Confirmar el gimnasio y el tiempo disponible cuando sean relevantes para preparar una sesión o una alternativa.
- Entregar el contexto pertinente al analista, al planificador y al optimizador, distinguiendo declaraciones del usuario de inferencias.
- No diagnosticar lesiones ni asumir recuperación a partir del rendimiento. Las decisiones de programación y cambios de rutina corresponden al planificador y al optimizador.

La frecuencia de las consultas y el canal de interacción quedan por acordar. Un formulario breve puede servir para la primera versión.

## Inventario y mapa por gimnasio

### Objetivo

Construir un inventario y un mapa de las máquinas y estaciones relevantes del gimnasio actual, con posibilidad de incorporar otro gimnasio después. Utilizar esa información al generar recomendaciones para que los ejercicios propuestos estén disponibles y el orden evite recorridos innecesarios entre zonas.

### Información propuesta

- **Gimnasio:** identificador propio, nombre y zonas o plantas. Cada sede mantiene su inventario y distribución.
- **Estación física:** identificador propio, nombre reconocible, tipo de equipo, ubicación o zona, accesorios y notas útiles. Foto y modelo pueden añadirse para distinguir máquinas similares.
- **Relaciones de cercanía:** estaciones en la misma zona, cercanas o separadas por un desplazamiento importante. Más adelante se pueden añadir posiciones en un plano y conexiones entre zonas, sin exigir medidas exactas para empezar.
- **Ejercicios compatibles:** asociación entre cada estación y los `exercise_template_id` de Hevy. Una estación puede admitir varios ejercicios y un ejercicio puede realizarse en varias estaciones.
- **Contexto de sesión:** gimnasio y, cuando se conozca, estación utilizada. Mantener esa distinción al comparar cargas entre máquinas distintas.

El catálogo de ejercicios de Hevy sirve como referencia para nombres e identificadores. El usuario señala que la app incluye imágenes; antes de depender de ellas en nuestra interfaz, verificar qué imágenes o videos expone la API y cómo pueden utilizarse. Una ilustración del ejercicio ayuda a identificar el movimiento, pero la máquina y su ubicación se confirman con el inventario del gimnasio.

### Uso por los agentes

- El planificador distribuye el trabajo según los gimnasios previstos y el equipo disponible en cada uno.
- El optimizador propone estaciones y un orden práctico, agrupando ejercicios cercanos y aprovechando estaciones compartidas cuando respete los objetivos y las preferencias. Por ejemplo, conservar juntos Chest Fly y Rear Delt Reverse Fly si se realizan en la misma máquina.
- El analista distingue cambios de máquina o gimnasio que afecten la comparación entre sesiones.
- El seguimiento recoge cambios de gimnasio y disponibilidad comunicados por el usuario. La ocupación o las averías no se consideran conocidas en tiempo real salvo que se registren.

### Primera versión propuesta

1. Relevar las máquinas utilizadas en B, D y E en el gimnasio actual, con zonas y cercanía aproximada.
2. Asociarlas a los ejercicios de Hevy y validar esas correspondencias con el usuario.
3. Mostrar un mapa sencillo o esquema por zonas y utilizarlo para explicar el recorrido de una rutina propuesta.
4. Ampliar el inventario al resto del equipo disponible e incorporar el segundo gimnasio cuando se conozca.

`gym space` es el mapa: un plano 3D con la forma real del gimnasio (contorno y secciones con nombre dibujados punto por punto, muros y puertas) donde se ubican las máquinas de todo el catálogo de Hevy, agrupadas por máquina física con su modelo 3D. `gym graph` es una función aparte que, con esas posiciones, calcula el grafo de cercanía con distancias caminando que rodean paredes y pasan por puertas, los metros de cada rutina y un orden que adelanta las máquinas ocupadas. `gym path` es su interfaz visual, en otra página: dibuja en 3D el recorrido de cada rutina sobre las máquinas, compara el orden actual con el propuesto y permite recorrerlo paso a paso. Falta relevar el gimnasio y definir cómo registrar el gimnasio de cada sesión.

## Colaboración e implementación por definir

Flujo conceptual: **sesiones → analista → planificador → optimizador → revisión del usuario → seguimiento de nuevas sesiones**. La investigación del planificador alimenta también al optimizador. No es necesario ejecutar todos los agentes tras cada sesión.

- **Contexto compartido:** datos de Hevy, preferencias confirmadas, contexto del cuarto agente, inventarios y mapas por gimnasio, reportes, plan vigente, versiones de rutinas y decisiones del usuario. Cada resultado debe indicar qué versiones utilizó.
- **Investigación compartida:** guardar fuentes, fecha de revisión, hallazgos y limitaciones para reutilizarlos entre agentes, evitando que investiguen lo mismo de forma independiente en cada ejecución.
- **Intercambios estructurados:** el seguimiento entrega contexto confirmado; el analista, observaciones y datos; el planificador, objetivos y criterios del bloque; el optimizador, cambios concretos para revisión. Las cifras se calculan con código.
- **Coordinación:** decidir qué tarea ejecutar según llegue una sesión, corresponda revisar un bloque o el usuario solicite optimizar una rutina. Puede comenzar como lógica de aplicación; no requiere un agente adicional de entrada.
- **Ejecución controlada:** evitar que varios agentes modifiquen simultáneamente la misma rutina y permitir reintentar una etapa sin duplicar propuestas o notificaciones.

Antes de elegir un framework, acordar estos intercambios, la información compartida, los disparadores y el presupuesto de ejecución.
