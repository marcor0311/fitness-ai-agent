# Documentación

- [Preferencias de entrenamiento](business/training-preferences.md): qué respetar al ajustar las rutinas.
- [Arquitectura](architecture/overview.md): datos, diagramas y decisiones que condicionan el proyecto.
- [Operación](operations/runbook.md): comandos y qué revisar cuando falta un entrenamiento.
- [Pendientes](backlog.md): siguientes pasos con un resultado comprobable.
- [Documentación oficial de la API de Hevy](https://api.hevyapp.com/docs/): referencia para la integración con Hevy.

## Estado · 13 de noviembre de 2026

La descarga local funciona. El receptor está en Cloudflare Free y suscrito en Hevy. Se verificó el recorrido completo con un entrenamiento nuevo de prueba: aviso recibido, detalle guardado y lectura privada correcta. Una reentrega válida respondió 200 en 0,16 s. La nube recibe únicamente entrenamientos nuevos y funciona con la computadora apagada.

## Criterio para documentar

Agregar contenido cuando ayude a usar, cambiar o diagnosticar algo. Mantener cada dato en un solo lugar, actualizar el archivo afectado y eliminar lo que dejó de aportar. El inicio está en el [README principal](../README.md) y el despliegue en [Cloudflare](../cloudflare/README.md).

Diagramas con fondo blanco, texto oscuro y SVG revisado. Secretos y entrenamientos completos permanecen fuera de la documentación.
