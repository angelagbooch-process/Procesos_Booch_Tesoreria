import streamlit as st
from datetime import date, datetime, timezone
from pathlib import Path
import json
import uuid
import csv
import io

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GOOGLE_SHEETS_AVAILABLE = True
except Exception:
    GOOGLE_SHEETS_AVAILABLE = False

st.set_page_config(
    page_title="Levantamiento de funciones — Yorlenis",
    page_icon="📋",
    layout="wide",
)

st.title("Levantamiento y validación de funciones")
st.caption("Piloto · Funciones de prioridad crítica · Respuestas → borrador de procedimiento → validación")

st.info(
    "Complete las respuestas según cómo se trabaja actualmente. La aplicación genera un borrador "
    "para revisar; no supone que existan autorizaciones o controles que no se hayan confirmado."
)

NO_SE = "No estoy segura"
OTRO = "Otro / Especificar"

# ID no secreto de la hoja de control creada para el piloto.
SPREADSHEET_ID = "1v8qaukYjo2JDWi_yqKBSZ5kWq0juqifhG7MZr1ii8Jc"
WORKSHEET_NAME = "Respuestas Yorlenis"
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

if "submission_session_id" not in st.session_state:
    st.session_state.submission_session_id = str(uuid.uuid4())

SHEET_HEADERS = [
    "registro_id", "fecha_guardado_utc", "fecha_levantamiento", "respondiente",
    "funcion", "respuestas_json", "validacion_yorlenis", "correcciones_yorlenis",
    "frecuencia", "duracion", "procedimiento_borrador", "estado",
]

@st.cache_resource(show_spinner=False)
def get_google_worksheet():
    """Conecta con Google Sheets usando los Secrets de Streamlit."""
    if not GOOGLE_SHEETS_AVAILABLE:
        raise RuntimeError("Faltan dependencias: gspread y google-auth. Revise requirements.txt.")
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("No se encuentra [gcp_service_account] en Streamlit Secrets.")
    creds_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_info, scopes=SHEETS_SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=len(SHEET_HEADERS))
    if not worksheet.get_all_values():
        worksheet.append_row(SHEET_HEADERS, value_input_option="RAW")
    else:
        first_row = worksheet.row_values(1)
        if first_row != SHEET_HEADERS:
            raise RuntimeError(
                f"La pestaña '{WORKSHEET_NAME}' ya tiene contenido o encabezados diferentes. "
                "No se modificó para proteger los datos existentes."
            )
    return worksheet

def save_response_to_sheets(record):
    """Inserta la respuesta o actualiza la misma función dentro de esta sesión."""
    worksheet = get_google_worksheet()
    existing_ids = worksheet.col_values(1)
    registro_id = record["registro_id"]
    if registro_id in existing_ids:
        row_num = existing_ids.index(registro_id) + 1
        worksheet.update(f"A{row_num}:L{row_num}", [record[header] for header in SHEET_HEADERS], value_input_option="RAW")
    else:
        worksheet.append_row([record[header] for header in SHEET_HEADERS], value_input_option="RAW")


def question(label, options, key, multi=False, help_text=None):
    if multi:
        return st.multiselect(label, options, key=key, help=help_text)
    return st.radio(label, options, key=key, horizontal=False, help=help_text)

def text_input(label, key, placeholder="Escriba aquí si aplica"):
    return st.text_input(label, key=key, placeholder=placeholder)

def choices_for_process(process):
    common_auth = [
        "Gerencia o jefe", "Asistente administrativo", "Contabilidad",
        "Responsable del área solicitante", "Otra persona",
        "No existe una autorización específica", NO_SE
    ]
    common_sources = [
        "Excel o listado entregado por otra persona", "Facturas y soportes",
        "Información extraída de un sistema o portal", "Correo electrónico",
        "Instrucciones del asistente administrativo", "Varias fuentes", OTRO
    ]
    if process == "ZOOM — pago de facturas y COD":
        return [
            ("¿Qué operaciones realiza usted?", [
                "Pago de facturas mediante transferencia bancaria",
                "Pago de COD desde el portal de ZOOM",
                "Ambas operaciones", OTRO
            ], True),
            ("¿De dónde obtiene la información para realizar los pagos?", [
                "Excel entregado por el asistente administrativo",
                "Soportes de retenciones entregados por el asistente administrativo",
                "Información consultada directamente en el portal de ZOOM",
                OTRO
            ], True),
            ("¿Quién autoriza o confirma qué operaciones deben pagarse?", common_auth, False),
            ("Después de pagar, ¿qué hace usted?", [
                "Guarda o imprime el comprobante bancario",
                "Adjunta los soportes en el portal de ZOOM",
                "Verifica que los archivos queden registrados correctamente",
                "Imprime o conserva facturas, retenciones o reportes COD",
                OTRO
            ], True),
            ("¿Quién recibe o archiva los documentos físicos?", [
                "El asistente administrativo", "Yorlenis", "Otra persona",
                "No existe una persona definida", NO_SE
            ], False),
            ("Si falta un soporte o hay una diferencia, ¿qué hace?", [
                "Solicita la información al asistente administrativo",
                "Consulta a la persona que autorizó el pago",
                "Resuelve la diferencia directamente con ZOOM",
                "Otro procedimiento", "No existe un procedimiento definido", NO_SE
            ], False),
        ]
    if process == "Consolidado semanal de proveedores":
        return [
            ("¿Qué información utiliza para preparar el consolidado?", common_sources, True),
            ("¿Qué hace usted con esa información?", [
                "Reúne los pagos pendientes en un solo listado",
                "Revisa importes y datos de los proveedores",
                "Organiza pagos por empresa, moneda o vencimiento",
                "Calcula o modifica importes", OTRO
            ], True),
            ("¿Quién recibe el consolidado para su aprobación?", [
                "Gerencia o jefe", "Asistente administrativo", "Contabilidad",
                "Otra persona", "No se envía para aprobación", NO_SE
            ], False),
            ("¿Qué sucede después de enviar el consolidado?", [
                "Recibo la aprobación y ejecuto los pagos",
                "Otra persona ejecuta los pagos",
                "Recibo cambios o instrucciones antes de pagar",
                "No hago seguimiento", OTRO
            ], False),
            ("¿Cómo deja constancia del trabajo realizado?", [
                "Archivo Excel", "Correo electrónico", "Comprobantes bancarios",
                "Sistema o plataforma", "No existe un registro específico", OTRO
            ], True),
        ]
    if process in ("Nómina quincenal — obreros y vigilantes",
                   "Nómina quincenal — tiendas, condominio y empresas"):
        groups = (process == "Nómina quincenal — tiendas, condominio y empresas")
        qs = []
        if groups:
            qs.append(("¿Qué entidades o grupos incluye esta función?", [
                "Personal de tiendas", "Personal de condominio", "Personal de Booch",
                "Personal de Bufecorp", "Personal de Baringco", OTRO
            ], True))
        qs += [
            ("¿Qué actividad realiza usted en el proceso?", [
                "Recibo la nómina preparada y realizo los pagos",
                "Reviso la información y preparo los pagos",
                "Calculo o preparo la nómina", "Realizo todo el proceso", OTRO
            ], False),
            ("¿Quién le entrega o prepara la información?", [
                "Asistente administrativo", "Recursos Humanos o responsable de personal",
                "Contabilidad", "Gerencia o jefe", "Responsables de empresas o tiendas",
                "Otra persona", NO_SE
            ], True),
            ("¿Quién revisa o autoriza los importes antes de pagar?", common_auth, False),
            ("¿Cómo se realizan los pagos?", [
                "Transferencias bancarias", "Pagos en efectivo",
                "Una combinación de ambos", OTRO
            ], False),
            ("¿Qué comprobantes o registros conserva?", [
                "Comprobantes bancarios", "Relación de pagos realizados",
                "Nómina utilizada para el pago", "Recibos firmados", OTRO,
                "No conservo un registro específico"
            ], True),
        ]
        return qs
    if process == "Pagos en línea — impuestos, condominios y servicios":
        return [
            ("¿Qué tipos de pagos realiza?", [
                "Impuestos", "Condominios", "Servicios públicos", OTRO
            ], True),
            ("¿Cómo recibe los datos para efectuar el pago?", [
                "Factura o recibo", "Instrucciones del asistente administrativo",
                "Instrucciones de gerencia o jefe", "Correo electrónico",
                "Consulta directamente el portal correspondiente", OTRO
            ], True),
            ("¿Quién autoriza que se realice el pago?", common_auth, False),
            ("Después de pagar, ¿qué hace con el comprobante?", [
                "Lo imprime", "Lo guarda digitalmente", "Lo envía por correo",
                "Lo entrega al asistente administrativo", "Lo adjunta en un sistema o portal",
                OTRO
            ], True),
            ("¿Cómo controla que no quede un pago pendiente o vencido?", [
                "Utilizo un calendario o listado de vencimientos",
                "Reviso las facturas o recibos recibidos",
                "Recibo recordatorios de otra persona",
                "No llevo un control específico", OTRO
            ], True),
        ]
    if process == "Pagos de compras de materiales":
        return [
            ("¿Qué recibe antes de realizar un pago?", [
                "Factura del proveedor", "Solicitud de pago", "Orden de compra",
                "Aprobación de gerencia o jefe", "Instrucciones del asistente administrativo", OTRO
            ], True),
            ("¿Qué hace antes de pagar?", [
                "Verifico el importe y los datos bancarios",
                "Compruebo que la factura corresponda a la solicitud",
                "Verifico que exista autorización",
                "Recibo la instrucción y ejecuto el pago", OTRO
            ], True),
            ("¿Quién autoriza el pago?", common_auth, False),
            ("¿Cómo realiza el pago?", [
                "Transferencia bancaria", "Pago en efectivo", OTRO
            ], False),
            ("¿Qué hace con el comprobante?", [
                "Lo envía al proveedor", "Lo envía al asistente administrativo",
                "Lo archiva junto con la factura", "Lo guarda digitalmente",
                "Realiza varias de estas acciones", OTRO
            ], True),
        ]
    if process == "Recibos de pagos en divisas — Bufecorp y Booch":
        return [
            ("¿Qué hace exactamente en esta función?", [
                "Preparo y emito recibos de pagos realizados",
                "Registro pagos en un sistema",
                "Verifico información para elaborar recibos",
                "Recibo datos preparados por otra persona y genero los recibos", OTRO
            ], True),
            ("¿Qué información utiliza para elaborar el recibo?", [
                "Comprobante de pago", "Factura o documento de cobro",
                "Información entregada por el asistente administrativo",
                "Información de un sistema", OTRO
            ], True),
            ("¿Quién entrega o confirma la información del pago?", [
                "Asistente administrativo", "Gerencia o jefe", "Contabilidad",
                "Otra persona", NO_SE
            ], False),
            ("¿Quién recibe el recibo una vez emitido?", [
                "Proveedor o beneficiario", "Asistente administrativo", "Contabilidad",
                "Gerencia o jefe", "Otra persona", NO_SE
            ], True),
            ("¿Dónde conserva el recibo y sus soportes?", [
                "Carpeta física por mes y empresa", "Carpeta digital", "Correo electrónico",
                "Sistema o plataforma", "Se imprime y se entrega para archivo", OTRO
            ], True),
        ]
    return []

def fmt(value):
    if isinstance(value, list):
        return ", ".join(value) if value else "Sin respuesta"
    return value if value else "Sin respuesta"

processes = [
    "ZOOM — pago de facturas y COD",
    "Consolidado semanal de proveedores",
    "Nómina quincenal — obreros y vigilantes",
    "Nómina quincenal — tiendas, condominio y empresas",
    "Pagos en línea — impuestos, condominios y servicios",
    "Pagos de compras de materiales",
    "Recibos de pagos en divisas — Bufecorp y Booch",
]

with st.sidebar:
    st.header("Datos del levantamiento")
    respondent = st.text_input("Nombre de quien responde", value="Yorlenis")
    date_done = st.date_input("Fecha", value=date.today())
    process = st.selectbox("Función a revisar", processes)
    st.caption("Complete una función por vez. Puede volver a esta lista para revisar otra.")

st.subheader(process)
st.write("Seleccione las respuestas. En las preguntas que permiten varias opciones, puede marcar más de una.")

answers = {}
questions = choices_for_process(process)
for i, (label, options, multi) in enumerate(questions, 1):
    with st.container(border=True):
        answers[label] = question(
            label, options, key=f"{process}_{i}", multi=multi
        )
        if OTRO in (answers[label] if isinstance(answers[label], list) else [answers[label]]):
            answers[f"Detalle — {label}"] = text_input(
                "Indique cuál", key=f"{process}_{i}_other"
            )

st.divider()
st.subheader("Validación del procedimiento")
st.caption("Estas respuestas permiten que Yorlenis revise el borrador generado y confirme si representa su trabajo real.")

with st.form(f"validation_{process}"):
    confirm = st.radio(
        "¿El borrador generado a partir de sus respuestas describe correctamente cómo trabaja actualmente?",
        ["Sí, lo describe correctamente", "Parcialmente; necesita correcciones", "No, no representa mi trabajo"],
        index=0,
    )
    missing = st.text_area(
        "¿Qué actividad, persona, documento o paso importante falta o debe corregirse? (opcional)",
        placeholder="Escriba solo lo que falta o está incorrecto…",
        height=90,
    )
    frequency = st.selectbox(
        "¿Con qué frecuencia realiza esta función?",
        ["Diariamente", "Semanalmente", "Quincenalmente", "Mensualmente", "Según se requiera", NO_SE],
    )
    duration = st.selectbox(
        "¿Cuánto tiempo le toma normalmente cada vez?",
        ["Menos de 15 minutos", "15–30 minutos", "31–60 minutos", "Más de 1 hora", "Depende del volumen", NO_SE],
    )
    submitted = st.form_submit_button("Generar / actualizar borrador", type="primary")

if submitted:
    st.session_state[f"validated_{process}"] = {
        "confirm": confirm, "missing": missing, "frequency": frequency, "duration": duration
    }

validation = st.session_state.get(f"validated_{process}", {})
st.divider()
st.header("Borrador de procedimiento para revisar")

def role_line(answer_values):
    vals = []
    for v in answer_values.values():
        vals.extend(v if isinstance(v, list) else [v])
    roles = []
    if any("asistente administrativo" in str(v).lower() for v in vals):
        roles.append("Asistente administrativo: entrega información o recibe documentación, según las respuestas seleccionadas.")
    if any("gerencia" in str(v).lower() or "jefe" in str(v).lower() for v in vals):
        roles.append("Gerencia o jefe: interviene en las instrucciones o autorizaciones cuando así se indicó.")
    if any("contabilidad" in str(v).lower() for v in vals):
        roles.append("Contabilidad: participa según la respuesta seleccionada.")
    roles.append("Yorlenis: realiza las actividades seleccionadas en este formulario.")
    return roles

st.markdown(f"**Función:** {process}")
st.markdown(f"**Responsable que responde:** {respondent or 'No indicado'}")
st.markdown(f"**Fecha:** {date_done.strftime('%d/%m/%Y')}")
st.markdown(f"**Frecuencia declarada:** {validation.get('frequency', 'Pendiente de confirmar')}")
st.markdown(f"**Duración declarada:** {validation.get('duration', 'Pendiente de confirmar')}")

st.markdown("### 1. Información y actividades declaradas")
for label, value in answers.items():
    st.markdown(f"- **{label}** {fmt(value)}")

st.markdown("### 2. Roles que aparecen en las respuestas")
for role in role_line(answers):
    st.markdown(f"- {role}")

st.markdown("### 3. Secuencia preliminar")
st.write(
    "1. Recibir o consultar la información indicada en las respuestas. "
    "2. Realizar las actividades seleccionadas para esta función. "
    "3. Ejecutar las verificaciones, comunicaciones o registros que se hayan seleccionado. "
    "4. Conservar o entregar los documentos según las respuestas."
)
st.caption(
    "La secuencia anterior es un esquema preliminar construido a partir de las respuestas; "
    "no confirma pasos que no se hayan descrito. Antes de aprobarlo, ajuste el texto si el orden real es diferente."
)

if validation:
    st.markdown("### 4. Validación de Yorlenis")
    st.markdown(f"- **Resultado:** {validation.get('confirm', 'Pendiente')}")
    st.markdown(f"- **Correcciones indicadas:** {validation.get('missing') or 'Ninguna indicada'}")

st.warning(
    "Pendiente de validación del responsable: comprobar que el orden de los pasos sea correcto, "
    "que los roles estén bien asignados y que no falten autorizaciones, verificaciones o documentos."
)

# Editable procedure text for review
default_procedure = f"""PROCEDIMIENTO: {process}

Responsable que responde: {respondent or 'Pendiente'}
Fecha: {date_done.strftime('%d/%m/%Y')}

OBJETIVO
Describir cómo se ejecuta actualmente esta función, de acuerdo con la información aportada por quien la realiza.

ENTRADAS Y ACTIVIDADES DECLARADAS
""" + "\n".join([f"- {k}: {fmt(v)}" for k, v in answers.items()]) + f"""

ROLES IDENTIFICADOS
""" + "\n".join([f"- {r}" for r in role_line(answers)]) + f"""

FRECUENCIA: {validation.get('frequency', 'Pendiente de confirmar')}
DURACIÓN: {validation.get('duration', 'Pendiente de confirmar')}

VALIDACIÓN DE LA RESPONSABLE
Resultado: {validation.get('confirm', 'Pendiente de confirmar')}
Correcciones: {validation.get('missing') or 'Pendiente de confirmar'}

PENDIENTES
- Confirmar el orden real de los pasos.
- Confirmar quién revisa y quién autoriza, si corresponde.
- Confirmar dónde se guarda la evidencia y quién la recibe.
"""
st.markdown("### 5. Texto editable para la validación final")
procedure_text = st.text_area(
    "Revise y corrija el procedimiento antes de descargarlo",
    value=default_procedure,
    height=360,
    key=f"procedure_text_{process}",
)
safe_name = process.lower().replace(" ", "_").replace("—", "").replace("/", "_")
registro_id = f"{st.session_state.submission_session_id}:{safe_name}"

if submitted:
    answers_json = json.dumps(answers, ensure_ascii=False)
    record = {
        "registro_id": registro_id,
        "fecha_guardado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fecha_levantamiento": date_done.isoformat(),
        "respondiente": respondent.strip(),
        "funcion": process,
        "respuestas_json": answers_json,
        "validacion_yorlenis": validation.get("confirm", "Pendiente"),
        "correcciones_yorlenis": validation.get("missing", ""),
        "frecuencia": validation.get("frequency", "Pendiente de confirmar"),
        "duracion": validation.get("duration", "Pendiente de confirmar"),
        "procedimiento_borrador": procedure_text,
        "estado": "Pendiente de revisión de Angela",
    }
    try:
        save_response_to_sheets(record)
        st.success("Respuesta guardada en Google Sheets. Puede cerrar la aplicación sin perder este registro.")
    except Exception as e:
        st.error("No se pudo guardar la respuesta en Google Sheets. No cierre esta pantalla hasta copiar o descargar el procedimiento.")
        st.caption(f"Detalle técnico: {type(e).__name__}: {e}")
st.download_button(
    "Descargar procedimiento en TXT",
    data=procedure_text.encode("utf-8"),
    file_name=f"procedimiento_{safe_name}.txt",
    mime="text/plain",
)
st.download_button(
    "Descargar respuestas en CSV",
    data=("Pregunta,Respuesta\n" + "\n".join(
        '"' + str(k).replace('"', '""') + '","' + fmt(v).replace('"', '""') + '"'
        for k, v in answers.items()
    )).encode("utf-8-sig"),
    file_name=f"respuestas_{safe_name}.csv",
    mime="text/csv",
)

st.caption(
    "Al pulsar «Generar / actualizar borrador», la aplicación intenta guardar las respuestas y el borrador en la pestaña "
    f"«{WORKSHEET_NAME}» de la hoja de control. Si aparece un error de guardado, descargue el procedimiento y avise a Angela."
)
