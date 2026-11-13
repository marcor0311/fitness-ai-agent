# Webhook de Hevy · Workers Free + D1 Free

Recibe **solo entrenamientos nuevos desde que se active la suscripción**. No carga rutinas, perfil, historial anterior ni los archivos locales de `data/`. No modifica nada en Hevy y no llama a modelos de IA de pago.

El despliegue usa una URL de `workers.dev`; no requiere comprar un dominio. Mantener la cuenta en **Workers Free**: no activar Workers Paid, Workers AI ni otros servicios de pago. Para 4–5 entrenamientos por semana se espera un consumo muy inferior a las cuotas gratuitas. Las cuotas y condiciones pueden cambiar; referencias oficiales al final.

## Flujo

1. Guardás un nuevo entrenamiento en Hevy.
2. Hevy envía `POST /webhooks/hevy` con `{ "workoutId": "…" }` y el encabezado Authorization que configurás.
3. El Worker valida la solicitud y guarda el ID en D1 antes de responder **200 OK**. No espera la consulta a Hevy para responder.
4. Un proceso en segundo plano consulta **solo** `GET https://api.hevyapp.com/v1/workouts/{workoutId}` y guarda ese entrenamiento en D1.
5. Si ese proceso falla o se interrumpe, una tarea programada cada cinco minutos recupera los eventos pendientes. No depende de tu computadora.
6. Los entrenamientos procesados se pueden consultar con `GET /api/workouts`, protegido por otro secreto. La sincronización Python existente sigue funcionando directamente contra Hevy y no envía datos a Cloudflare.

Los avisos duplicados se reconocen por workoutId. Se usan reintentos con espera y reservas temporales para recuperar procesos interrumpidos. D1 conserva los eventos pendientes: no dependen de una cola con vencimiento de 24 horas. Esta primera versión no genera recomendaciones ni notificaciones al usuario.

## Estado actual

**Desplegado y suscrito en Hevy el 13 de noviembre de 2026.** Se verificó en el panel que la cuenta usa Workers Free ($0). URL de recepción:

```text
https://fitness-hevy-webhook.fitness-hevy-webhook.workers.dev/webhooks/hevy
```

Base D1 creada y migrada, secretos configurados y recuperación de pendientes activa cada cinco minutos. Se verificaron por HTTPS el estado público, el rechazo de lectura sin autorización, la lectura privada y el rechazo de avisos inválidos. La URL y el encabezado de la suscripción persistieron en Hevy después de recargar.

**Recorrido completo verificado con un entrenamiento nuevo de prueba creado por el usuario en Hevy:** aviso recibido, estado `processed`, detalle guardado y lectura privada correcta. Una reentrega controlada respondió 200 en 0,158 s y no duplicó la sesión. No se importó historial anterior. Evidencia y secretos permanecen en `../data/`, excluido de Git; la configuración para Hevy está en `../data/hevy-webhook.txt`.

La prueba detectó y permitió corregir una incompatibilidad de consulta: Workers requiere `redirect: "manual"`, con rechazo explícito de respuestas 3xx mediante `response.ok`; `redirect: "error"` provoca un error antes de enviar la solicitud. La corrección está desplegada y cubierta por pruebas.

## Preparar y desplegar

Desde esta carpeta (`cloudflare/`), usando Node.js 22 o posterior:

```sh
npm ci --ignore-scripts
npx wrangler login
```

Crear una cuenta en <https://dash.cloudflare.com/sign-up> si todavía no existe. El inicio de sesión de Wrangler abre el navegador: iniciá sesión y autorizá la conexión. Nunca pegues credenciales de Cloudflare en el chat.

Crear la base de datos en la cuenta gratuita:

```sh
npx wrangler d1 create fitness-hevy
```

Copiar el `database_id` que devuelve ese comando en `wrangler.jsonc`, sustituyendo `REEMPLAZAR_CON_ID_DE_D1`. Si ya existe la base, usar su ID en vez de crear otra. Luego:

```sh
npm run db:remote
npm run deploy
```

El Worker todavía rechazará peticiones de datos hasta que se configuren los secretos. Configurarlos desde una terminal interactiva o desde el panel de Cloudflare:

```sh
npx wrangler secret put HEVY_API_KEY
npx wrangler secret put HEVY_WEBHOOK_AUTH
npx wrangler secret put READ_API_AUTH
```

- `HEVY_API_KEY`: tu clave actual de Hevy Pro. El código solo la usa para consultar el entrenamiento cuyo ID llegó en el webhook. La clave de Hevy tiene permisos más amplios que las operaciones que usa este receptor.
- `HEVY_WEBHOOK_AUTH`: encabezado completo, por ejemplo `Bearer <secreto-aleatorio>`. Es un secreto nuevo; **no usar la API key de Hevy en este campo**.
- `READ_API_AUTH`: otro encabezado completo `Bearer <otro-secreto-aleatorio>`, diferente del anterior. Permite leer los entrenamientos guardados.

Para generar cada secreto aleatorio se puede usar `openssl rand -hex 32` en la terminal y anteponer `Bearer `. Guardar los dos valores en un gestor de contraseñas y en Cloudflare Secrets; no en archivos versionados.

## Configurar la suscripción en Hevy

Después de desplegar y verificar el endpoint:

- **URL:** `https://<worker>.<tu-subdominio>.workers.dev/webhooks/hevy`. Usar la URL real que devuelve Wrangler, no este ejemplo.
- **Authorization header:** el valor completo de `HEVY_WEBHOOK_AUTH`, incluido `Bearer `.
- Pulsar **Subscribe**.

La confirmación de un aviso válido se midió en 0,158 s mediante reentrega del dummy existente. Es una medición de esta prueba, no una garantía de latencia para todas las peticiones.

El texto proporcionado por Hevy solo documenta avisos de entrenamientos nuevos. No se presupone que envíe cambios o eliminaciones ni que reintente entregas fallidas. Si un aviso nunca llega, no habrá evento que recuperar; la sincronización directa con Hevy sirve para comprobar el historial posteriormente.

## Consulta privada

`GET /api/workouts` requiere el encabezado `Authorization` con el valor de `READ_API_AUTH`.

Devuelve:

```json
{
  "workouts": [],
  "cursor": "0",
  "has_more": false
}
```

Devuelve hasta 50 entrenamientos por página, en orden de incorporación a D1. Para continuar, enviar `?cursor=<cursor-devuelto>`. Guardar el cursor solo después de guardar localmente los resultados. No existe un comando Python de descarga desde Cloudflare todavía; esta API permite conectarlo cuando se necesite.

`GET /health` es público y solo confirma que el Worker responde; no verifica Hevy, D1 ni los secretos. Los datos y los estados internos no son públicos. No se habilita CORS para aplicaciones externas.

## Pruebas locales

```sh
npm test
npm run db:local
```

Para levantar el Worker, copiar `dev.vars.example` a `.dev.vars`, completar secretos locales y ejecutar `npm run dev`. `.dev.vars`, `.wrangler` y `node_modules` están excluidos de Git. Para pruebas de recepción se puede dejar vacía la API key: el evento queda pendiente con `missing_hevy_api_key` en lugar de consultar Hevy.

Las pruebas usan SQLite real en memoria y la API de Hevy simulada. Comprueban que se responde antes de terminar la consulta externa, autenticación, payloads inválidos, fallos de almacenamiento, duplicados, reintentos, recuperación tras interrupciones y paginación. Nunca hacen llamadas reales a Hevy ni a Cloudflare.

## Coste y límites

El diseño solo utiliza Workers y D1 incluidos en el plan Free. No puede garantizar disponibilidad ilimitada ni que Cloudflare conserve las condiciones actuales. En Free, alcanzar las cuotas bloquea operaciones; no activa una mejora de plan mediante este código. El despliegue necesita comprobar que la cuenta siga en Free.

- [Límites de Workers](https://developers.cloudflare.com/workers/platform/limits/).
- [Precios y cuotas de D1](https://developers.cloudflare.com/d1/platform/pricing/).
- [Bloqueo al alcanzar cuotas gratuitas de D1](https://developers.cloudflare.com/changelog/post/2026-09-01-d1-free-tier-limit-enforcement/).
- [Alcance y duración de waitUntil](https://developers.cloudflare.com/workers/runtime-apis/context/).
- [Tareas programadas](https://developers.cloudflare.com/workers/configuration/cron-triggers/).
