# Pendientes

## Siguiente

- [x] **Comprobar el webhook completo:** validado con el dummy nuevo creado por el usuario en Hevy; quedó `processed`, se leyó su detalle y una reentrega respondió 200 en 0,16 s sin duplicarlo.
- [x] **Aplicar preferencias al informe:** `sync` lee `data/preferences.json`, separa las series previstas de las guardadas como referencia y compara las dos últimas sesiones de D por ejercicio.
- [ ] **Revisar D después de probarla:** primera revisión hecha con las sesiones del 14 de octubre y el 13 de noviembre, en `data/D-review-2026-11-13.md`. Falta confirmar por qué no se registraron T-Bar Row ni Incline Curl, el tiempo disponible por sesión y empezar a registrar RPE. Repetir la comparación después de la próxima D completa.
- [ ] **Registro en Hevy:** el historial tiene 228 sesiones anteriores, pero solo tres de B, D y E en 12 semanas y una en los 28 días previos al 13 de noviembre, frente a cuatro por semana declaradas. Confirmar si faltan registros antes de evaluar volumen o tendencias.

## Después

- [x] Descargar entrenamientos de Cloudflare desde el CLI, guardando antes de avanzar el cursor: `python3 -m fitness_agent pull`.
- [ ] Definir retención y tratamiento de ediciones, eliminaciones y avisos no entregados. Caso concreto: el entrenamiento `test` de la prueba sigue en D1 aunque ya no está en Hevy.
- [x] Convertir los cambios puntuales de rutina en una operación reproducible con respaldo y verificación: `routine export` y `routine apply`.

## Agentes ([borrador](draft.md))

- [x] Reporte calculado por entrenamiento: `report`, con las seis secciones, versión, huella e idempotencia.
- [x] Espacio 3D por gimnasio: `gym space`, con las máquinas del catálogo de Hevy como modelos 3D.
- [x] Forma del gimnasio en `gym space`: contorno y secciones dibujados punto por punto, muros, puertas y paredes sueltas; el grafo mide caminando por esa forma y asigna cada máquina a su sección.
- [ ] Dibujar la forma real del gimnasio actual, ubicar sus máquinas y anotar su ocupación habitual.
- [x] Grafo de cercanía: `gym graph`, con metros por rutina y orden propuesto.
- [x] Recorrido 3D por rutina: `gym path`, página aparte de solo lectura con el orden actual, la propuesta y el camino por las puertas.
- [ ] Elegir modelo, entorno y presupuesto para completar la interpretación y las próximas acciones del reporte.
- [ ] Elegir el canal de aviso (app, Telegram o Gmail API) y dónde se consultan los reportes.
- [ ] Decidir si los reportes se generan en la nube y cómo llegan historial, rutinas y preferencias.
