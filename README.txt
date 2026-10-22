# Formularios Streamlit — Levantamiento de funciones de Yorlenis

## Contenido
- `app.py`: formularios, borrador de procedimiento y guardado en Google Sheets.
- `requirements.txt`: dependencias (Streamlit, gspread, google-auth).

## Requisitos
- Python 3.10 o posterior (recomendado 3.10–3.12).
- Navegador moderno (Chrome, Edge, Firefox o Safari).
- Cuenta de servicio de Google con permiso de edición sobre la hoja de control.

## Cómo ejecutarla (local)
1. Instale Python 3.10 o posterior.
2. Abra una terminal en la carpeta del proyecto.
3. Instale dependencias: `pip install -r requirements.txt`
4. Configure los Secrets de Google (sección siguiente).
5. Inicie la aplicación: `streamlit run app.py`

## Configuración de Google Sheets
Cree `.streamlit/secrets.toml` (local) o configure los Secrets en Streamlit Cloud:

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."

Comparta la hoja de Google Sheets con el `client_email` de la cuenta de servicio
con permiso de edición. La hoja y la pestaña se identifican en `app.py`
(`SHEET_ID` y `SHEET_NAME`).

## Uso
- Seleccione la función en la barra lateral.
- Responda las preguntas (incluye bloque de información bancaria y de control).
- Pulse «Generar / actualizar borrador».
- Revise y corrija el texto del procedimiento.
- Vuelva a pulsar «Generar / actualizar borrador» si editó el texto y quiere guardar cambios.
- Descargue el TXT y el CSV antes de cerrar.

## Qué se guarda en Google Sheets
Una fila por respondiente y función con las columnas:
registro_id, fecha_guardado_utc, fecha_levantamiento, respondiente, funcion,
respuestas_json, validacion_yorlenis, correcciones_yorlenis, frecuencia,
duracion, procedimiento_borrador, estado.

El `registro_id` es estable (`respondiente::funcion`): reenviar la misma función
actualiza la fila existente en lugar de duplicarla.

## Preguntas añadidas (información bancaria y de control)
Cada función incluye ahora un bloque transversal que captura:
- Banco(s) o portal(es) desde donde se paga.
- Canal usado con más frecuencia (transferencia, archivo plano, efectivo, portal).
- Frecuencia de pago por banco/portal.
- Quién más tiene acceso o puede autorizar en esas cuentas.
- Verificación de datos bancarios del proveedor antes de pagar.
- Quién confirma que el pago se realizó.
- Existencia de monto máximo sin autorización adicional.
- Procedimiento ante fallo del pago.

Además, cada función tiene preguntas específicas (ej. nómina: archivo plano y
manejo de efectivo; ZOOM: frecuencia de pagos COD; compras: verificación de
recepción de mercancía).

## Importante
Versión piloto. El guardado en Google Sheets requiere los Secrets configurados y
permisos sobre la hoja. Si el guardado falla, la aplicación muestra un error y ofrece
un botón de reintento; descargue siempre el TXT y el CSV como respaldo.

Para enviarla a Yorlenis desde otro equipo, publíquela en un servicio accesible
(por ejemplo, Streamlit Community Cloud) o ejecútela en un equipo servidor con acceso
de red. No comparta públicamente información financiera sensible sin acordar antes
quién puede acceder a ella.

## Checklist antes de entregar
- [ ] `streamlit run app.py` arranca sin errores.
- [ ] Secrets de Google configurados y hoja accesible.
- [ ] Guardar una respuesta de prueba crea la fila en la hoja.
- [ ] Reenviar el mismo proceso actualiza la fila (no duplica).
- [ ] TXT y CSV se descargan correctamente con comas y saltos de línea.
- [ ] Editar el texto y reenviar actualiza `procedimiento_borrador`.
- [ ] Las preguntas bancarias aparecen en todas las funciones y se guardan en `respuestas_json`.