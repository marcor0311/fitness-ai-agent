# Documentación

- [Preferencias de entrenamiento](business/training-preferences.md): qué respetar al ajustar las rutinas.
- [Arquitectura](architecture/overview.md): datos, diagramas y decisiones que condicionan el proyecto.
- [Operación](operations/runbook.md): comandos y qué revisar cuando falta un entrenamiento.
- [Pendientes](backlog.md): siguientes pasos con un resultado comprobable.
- [Borrador de posibles agentes](draft.md): candidatos, alcance propuesto y decisiones abiertas antes de implementar.
- [Documentación oficial de la API de Hevy](https://api.hevyapp.com/docs/): referencia para la integración con Hevy.

## Estado · 17 de noviembre de 2026

La descarga local funciona y el informe aplica las preferencias. El receptor está en Cloudflare Free y suscrito en Hevy; se verificó el recorrido completo con un entrenamiento nuevo de prueba. `pull` descarga lo recibido y `report` genera el reporte calculado de cada entrenamiento, sin IA todavía. Los cambios de rutina se aplican con `routine apply`, con respaldo y verificación. `gym space` permite dibujar el plano del gimnasio (contorno, secciones con muros y puertas) y ubicar en 3D las máquinas del catálogo de Hevy; `gym graph` calcula la cercanía caminando y el orden por rutina, y `gym path` muestra ese recorrido en 3D en una página aparte. Falta relevar el gimnasio real.

## Criterio para documentar

Agregar contenido cuando ayude a usar, cambiar o diagnosticar algo. Mantener cada dato en un solo lugar, actualizar el archivo afectado y eliminar lo que dejó de aportar. El inicio está en el [README principal](../README.md) y el despliegue en [Cloudflare](../cloudflare/README.md).

Diagramas con fondo blanco, texto oscuro y SVG revisado. Secretos y entrenamientos completos permanecen fuera de la documentación.
