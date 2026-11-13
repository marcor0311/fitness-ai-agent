# Operación

## Comandos habituales

| Tarea | Dónde | Comando |
| --- | --- | --- |
| Conectar Hevy | Raíz | `python3 -m fitness_agent setup` |
| Descargar B, D y E | Raíz | `python3 -m fitness_agent sync` |
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

Consultar las [preferencias](../business/training-preferences.md). `sync` reemplaza snapshot e informe y todavía no incorpora automáticamente `data/preferences.json`. El informe tampoco descuenta el Iso-Lateral omitido: distinguir sus dos series guardadas de las que se realizan.

El CLI implementa solo lectura. Los cambios puntuales en Hevy deben conservar respaldo y verificarse con una nueva consulta; los respaldos están en `data/changes/`. No deducir progreso de una sola sesión o únicamente del tonelaje.
