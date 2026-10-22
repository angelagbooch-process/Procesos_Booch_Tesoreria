import csv
import io
import json
from datetime import date, datetime, timezone

import streamlit as st

try:
    import gspread
    from google.oauth2.service_account import Credentials
    SHEETS_OK = True
except ImportError:
    SHEETS_OK = False

st.set_page_config(
    page_title="Levantamiento de funciones — Tesorería",
    page_icon="📋",
    layout="wide",
)

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Define aquí la contraseña para que solo tú (Angela) puedas ver el borrador y descargar.
PASSWORD_ADMIN = "AngelaAdmin2026"  # <--- Cámbiala por una tuya

st.title("Levantamiento y validación de funciones")
st.caption("Piloto · Funciones de prioridad crítica")

NO_SE = "No estoy segura"
OTRO = "Otro / Especificar"
SHEET_ID = "1v8qaukYjo2JDWi_yqKBSZ5kWq0juqifhG7MZr1ii8Jc"
SHEET_NAME = "Respuestas Yorlenis"

SHEET_HEADERS = [
    "registro_id", "fecha_guardado_utc", "fecha_levantamiento", "respondiente",
    "funcion", "respuestas_json", "validacion_yorlenis", "correcciones_yorlenis",
    "frecuencia", "duracion", "procedimiento_borrador", "estado",
]

# ---------- Google Sheets ----------

@st.cache_resource(show_spinner=False)
def get_worksheet():
    if not SHEETS_OK:
        raise RuntimeError("Faltan dependencias: gspread y google-auth.")
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("Falta [gcp_service_account] en Streamlit Secrets.")
    
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
    )
    spreadsheet = gspread.authorize(creds).open_by_key(SHEET_ID)
    
    try:
        ws = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(SHEET_HEADERS))
    
    if not ws.cell(1, 1).value:
        ws.append_row(SHEET_HEADERS, value_input_option="RAW")
        
    return ws

def save_record(record):
    ws = get_worksheet()
    row = [record[h] for h in SHEET_HEADERS]
    ids = ws.col_values(1)
    if record["registro_id"] in ids:
        n = ids.index(record["registro_id"]) + 1
        try:
            ws.update(f"A{n}:L{n}", [row], value_input_option="RAW")
        except TypeError:
            ws.update(f"A{n}:L{n}", [row], params={"valueInputOption": "RAW"})
    else:
        ws.append_row(row, value_input_option="RAW")

# ---------- Listas reutilizables ----------

AUTH = [
    "Gerencia o jefe", "Asistente administrativo", "Contabilidad",
    "Responsable del área solicitante", "Otra persona",
    "No existe una autorización específica", NO_SE,
]
SOURCES = [
    "Excel o listado entregado por otra persona", "Facturas y soportes",
    "Información extraída de un sistema o portal", "Correo electrónico",
    "Instrucciones del asistente administrativo", "Varias fuentes", OTRO,
]
BANCOS = [
    "Banco Nacional de Crédito (BNC)", "Banesco", "Mercantil", "Provincial", 
    "Bancamiga", "Banco de Venezuela", "Portal de ZOOM", "Portal de impuestos", OTRO, NO_SE
]
CANALES = [
    "Transferencia interbancaria desde portal del banco",
    "Transferencia mismo banco",
    "Pago masivo con archivo plano",
    "Pago en efectivo en taquilla",
    "Pago desde portal web del proveedor/servicio",
    "Pago desde el portal de ZOOM",
    OTRO, NO_SE,
]
FRECUENCIAS = [
    "Diaria", "Semanal", "Quincenal", "Mensual",
    "Solo cuando se requiere", "Varía según el tipo de pago", NO_SE,
]

BLOQUE_BANCARIO = [
    ("¿Desde qué banco(s) o portal(es) realiza los pagos de esta función?", BANCOS, True),
    ("¿Qué número de cuenta (y tipo de cuenta) usa en cada banco o portal?", [], False), # Pregunta de texto libre
    ("¿Qué canal usa con más frecuencia en cada banco/portal?", CANALES, True),
    ("¿Con qué frecuencia paga desde cada banco/portal?", FRECUENCIAS, True),
    ("¿Quién más tiene acceso o puede autorizar pagos en esas cuentas?", [
        "Solo el responsable", "El responsable y el asistente administrativo",
        "El responsable y gerencia", "Varias personas", NO_SE,
    ], False),
    ("Antes de pagar, ¿verifica que los datos bancarios del proveedor sean correctos?", [
        "Siempre, contra factura o registro", "A veces", "Nunca",
        "No aplica (pago a entidad fija)", NO_SE,
    ], False),
    ("¿Quién confirma que el pago se realizó correctamente?", [
        "Yo misma reviso el comprobante", "Otra persona revisa",
        "No se confirma formalmente", NO_SE,
    ], False),
    ("¿Existe un monto máximo que puede pagar sin autorización adicional?", [
        "Sí (indicar monto aproximado en 'Otro')", "No", NO_SE,
    ], False),
    ("Si el pago no se puede ejecutar (fondos, error del portal, rechazo), ¿qué hace?", [
        "Aviso a gerencia o asistente", "Reintento más tarde",
        "Solicito instrucción", OTRO, NO_SE,
    ], False),
]

QUESTIONS = {
    "ZOOM — pago de facturas y COD": [
        ("¿Qué operaciones realiza usted?", [
            "Pago de facturas mediante transferencia bancaria",
            "Pago de COD desde el portal de ZOOM",
            "Ambas operaciones", OTRO,
        ], True),
        ("¿De dónde obtiene la información para realizar los pagos?", [
            "Excel entregado por el asistente administrativo",
            "Soportes de retenciones entregados por el asistente administrativo",
            "Información consultada directamente en el portal de ZOOM", OTRO,
        ], True),
        ("¿Quién autoriza o confirma qué operaciones deben pagarse?", AUTH, False),
        ("¿Los pagos COD se hacen desde el portal de ZOOM o desde un banco?", [
            "Solo desde el portal de ZOOM", "Solo desde banco",
            "Ambos según el caso", OTRO,
        ], False),
        ("¿Con qué frecuencia se generan pagos COD?", FRECUENCIAS, False),
        ("Después de pagar, ¿qué hace usted?", [
            "Guarda o imprime el comprobante bancario",
            "Adjunta los soportes en el portal de ZOOM",
            "Verifica que los archivos queden registrados correctamente",
            "Imprime o conserva facturas, retenciones o reportes COD", OTRO,
        ], True),
        ("¿Quién recibe o archiva los documentos físicos?", [
            "El asistente administrativo", "El responsable", "Otra persona",
            "No existe una persona definida", NO_SE,
        ], False),
        ("Si falta un soporte o hay una diferencia, ¿qué hace?", [
            "Solicita la información al asistente administrativo",
            "Consulta a la persona que autorizó el pago",
            "Resuelve la diferencia directamente con ZOOM",
            "Otro procedimiento", "No existe un procedimiento definido", NO_SE,
        ], False),
    ] + BLOQUE_BANCARIO,
    
    # Puedes ir agregando las demás funciones aquí...
}

# ---------- Utilidades ----------

def fmt(value):
    if isinstance(value, list):
        return ", ".join(value) if value else "Sin respuesta"
    return str(value) if value not in (None, "") else "Sin respuesta"

def roles_from(answers):
    selected = {str(v).strip().lower() for val in answers.values()
                for v in (val if isinstance(val, list) else [val])}
    roles = []
    if "asistente administrativo" in selected:
        roles.append("Asistente administrativo: entrega información o recibe documentación.")
    if "gerencia o jefe" in selected:
        roles.append("Gerencia o jefe: instruye o autoriza cuando así se indicó.")
    if "contabilidad" in selected:
        roles.append("Contabilidad: participa según la respuesta seleccionada.")
    roles.append("Responsable de Tesorería: realiza las actividades seleccionadas.")
    return roles

def safe_name(process):
    s = process.lower()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")]:
        s = s.replace(a, b)
    return s.replace(" ", "_").replace("—", "").replace("/", "_")

def build_procedure(process, respondent, date_done, answers, validation):
    lines = [
        f"PROCEDIMIENTO: {process}",
        f"Responsable: {respondent or 'Pendiente'}",
        f"Fecha: {date_done.strftime('%d/%m/%Y')}",
        "",
        "OBJETIVO",
        "Describir cómo se ejecuta actualmente esta función.",
        "",
        "ENTRADAS Y ACTIVIDADES DECLARADAS",
        *[f"- {k}: {fmt(v)}" for k, v in answers.items()],
        "",
        "ROLES IDENTIFICADOS",
        *[f"- {r}" for r in roles_from(answers)],
        "",
        "INFORMACIÓN BANCARIA Y DE CONTROL",
        *[f"- {k}: {fmt(v)}" for k, v in answers.items()
          if any(x in k for x in ("banco", "portal", "canal", "frecuencia", "acceso",
                                  "datos bancarios", "confirma", "monto máximo",
                                  "no se puede ejecutar", "número de cuenta"))],
        "",
        f"FRECUENCIA GENERAL: {validation.get('frequency', 'Pendiente de confirmar')}",
        f"DURACIÓN: {validation.get('duration', 'Pendiente de confirmar')}",
        "",
        "VALIDACIÓN DEL RESPONSABLE",
        f"Resultado: {validation.get('confirm', 'Pendiente de confirmar')}",
        f"Correcciones: {validation.get('missing') or 'Pendiente de confirmar'}",
        "",
        "PENDIENTES",
        "- Confirmar el orden real de los pasos.",
        "- Confirmar quién revisa y quién autoriza, si corresponde.",
    ]
    return "\n".join(lines)

def answers_csv(answers):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Pregunta", "Respuesta"])
    for k, v in answers.items():
        writer.writerow([k, fmt(v)])
    return buf.getvalue().encode("utf-8-sig")

# ---------- Interfaz ----------

with st.sidebar:
    st.header("Datos del levantamiento")
    respondent = st.text_input("Cargo de quien responde", value="Responsable de Tesorería")
    date_done = st.date_input("Fecha", value=date.today())
    process = st.selectbox("Función a revisar", list(QUESTIONS.keys()))
    
    st.divider()
    st.subheader("Acceso Administrador")
    password = st.text_input("Contraseña (solo Angela)", type="password")
    is_admin = (password == PASSWORD_ADMIN)

st.subheader(process)
st.write("Seleccione las respuestas. En las preguntas que permiten varias opciones, puede marcar más de una.")

answers = {}
for i, (label, options, multi) in enumerate(QUESTIONS[process], 1):
    with st.container(border=True):
        key = f"{process}_{i}"
        
        # Detectar si es la pregunta de número de cuenta
        if "número de cuenta" in label.lower():
            answers[label] = st.text_area(
                label, key=key, placeholder="Ej: Banesco - Cuenta Corriente 0102-xxxx-xxxx"
            )
        else:
            answers[label] = (
                st.multiselect(label, options, key=key, placeholder="Seleccione opciones")
                if multi else
                st.radio(label, options, key=key, horizontal=False)
            )
            selected = answers[label] if isinstance(answers[label], list) else [answers[label]]
            
            # Mostrar campo "Otro" o "Monto"
            if OTRO in selected or "monto máximo" in label.lower():
                answers[f"Detalle — {label}"] = st.text_input(
                    "Indique cuál o el monto", key=f"{key}_other", placeholder="Escriba aquí"
                )

st.divider()
st.subheader("Validación del procedimiento")
st.caption("Estas respuestas permiten confirmar si el proceso descrito representa el trabajo real.")

with st.form(f"validation_{process}"):
    confirm = st.radio(
        "¿El proceso descrito refleja cómo trabaja actualmente?",
        ["Sí, lo describe correctamente", "Parcialmente; necesita correcciones", "No, no representa mi trabajo"],
        index=0,
    )
    missing = st.text_area(
        "¿Qué actividad, persona o paso importante falta o debe corregirse? (opcional)",
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
    submitted = st.form_submit_button("Enviar y guardar respuestas", type="primary")

if submitted:
    st.session_state[f"validated_{process}"] = {
        "confirm": confirm, "missing": missing,
        "frequency": frequency, "duration": duration,
    }
    st.session_state.pop(f"procedure_text_{process}", None)

validation = st.session_state.get(f"validated_{process}", {})
default_procedure = build_procedure(process, respondent, date_done, answers, validation)
slug = safe_name(process)
registro_id = f"tesoreria::{slug}"

# Lógica de guardado
if submitted:
    record = {
        "registro_id": registro_id,
        "fecha_guardado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fecha_levantamiento": date_done.isoformat(),
        "respondiente": respondent.strip(),
        "funcion": process,
        "respuestas_json": json.dumps(answers, ensure_ascii=False),
        "validacion_yorlenis": validation.get("confirm", "Pendiente"),
        "correcciones_yorlenis": validation.get("missing", ""),
        "frecuencia": validation.get("frequency", "Pendiente de confirmar"),
        "duracion": validation.get("duration", "Pendiente de confirmar"),
        "procedimiento_borrador": default_procedure,
        "estado": "Pendiente de revisión de Angela",
    }
    try:
        save_record(record)
        st.success("✅ Respuestas guardadas correctamente. Gracias por su tiempo.")
    except Exception as e:
        st.session_state["pending_record"] = record
        st.error("No se pudo guardar en la base de datos. Por favor, avise a Angela.")
        st.caption(f"Detalle: {type(e).__name__}: {e}")

if "pending_record" in st.session_state:
    if st.button("Reintentar guardado"):
        try:
            save_record(st.session_state["pending_record"])
            st.success("Registro pendiente guardado.")
            del st.session_state["pending_record"]
        except Exception as e:
            st.error(f"Sigue fallando: {type(e).__name__}: {e}")

# --- ZONA EXCLUSIVA PARA EL ADMINISTRADOR (ANGELA) ---
if is_admin:
    st.divider()
    st.header("🔒 Zona de Administrador")
    st.info("Esta sección solo es visible para ti. Puedes revisar y editar el borrador generado.")
    
    st.markdown("### Borrador de procedimiento")
    procedure_text = st.text_area(
        "Revise y corrija el procedimiento antes de descargarlo",
        value=default_procedure,
        height=420,
        key=f"procedure_text_{process}",
    )
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Descargar procedimiento en TXT",
            data=procedure_text.encode("utf-8"),
            file_name=f"procedimiento_{slug}.txt",
            mime="text/plain",
        )
    with col2:
        st.download_button(
            "Descargar respuestas en CSV",
            data=answers_csv(answers),
            file_name=f"respuestas_{slug}.csv",
            mime="text/csv",
        )