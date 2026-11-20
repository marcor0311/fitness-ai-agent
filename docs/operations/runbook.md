# Operación

## Comandos habituales

| Tarea | Dónde | Comando |
| --- | --- | --- |
| Conectar Hevy | Raíz | `python3 -m fitness_agent setup` |
| Descargar B, D y E | Raíz | `python3 -m fitness_agent sync` |
| Descargar lo recibido por el webhook | Raíz | `python3 -m fitness_agent pull` |
| Reportar entrenamientos nuevos | Raíz | `python3 -m fitness_agent report` |
| Cambiar una rutina | Raíz | `routine export` → editar → `routine apply` → `--confirm` |
| Ubicar máquinas en 3D | Raíz | `python3 -m fitness_agent gym space` |
| Distancias y orden por cercanía | Raíz | `python3 -m fitness_agent gym graph` |
| Ver el recorrido de cada rutina en 3D | Raíz | `python3 -m fitness_agent gym path` |
| Pruebas Python | Raíz | `python3 -m unittest discover -s tests -v` |
| Pruebas del receptor | `cloudflare/` | `npm test` |

El [README de Cloudflare](../../cloudflare/README.md) contiene despliegue, secretos y URL. Mantener la cuenta en Free.

## Si falta un entrenamiento

1. Confirmar que se guardó en Hevy y que la suscripción conserva URL y autorización.
2. Comprobar `/health`; solo verifica el Worker, no Hevy ni D1.
3. Desde `cloudflare/`, revisar los eventos:

   ```sh
   npx wrangler d1 execute DB --remote --command "SELECT status, COUNT(*) AS total FROM webhook_events GROUP BY status;"
   ```

4. Si está pendiente, revisar `last_error`, `attempts` y `next_attempt_at`. El cron recupera reservas vencidas. Si está procesado, revisar la lectura privada y su cursor.
5. Si no existe evento, no hay recuperación automática. La sincronización local permite consultar Hevy sin subir ese historial a Cloudflare.

## Al revisar rutinas

Consultar las [preferencias](../business/training-preferences.md). `sync` reemplaza snapshot e informe y aplica `data/preferences.json`: el Iso-Lateral figura como referencia y sus dos series no cuentan como previstas. Si se cambia una omisión en Hevy, actualizar también ese archivo; el informe avisa si una omisión ya no existe en la rutina.

Los cambios en Hevy se hacen con `routine apply`: primero sin `--confirm` para revisar las diferencias. Si informa que la rutina cambió desde la exportación, exportar de nuevo y repetir la edición. Los respaldos de `data/changes/` pueden borrarse cuando el resultado esté comprobado. No deducir progreso de una sola sesión o únicamente del tonelaje.
