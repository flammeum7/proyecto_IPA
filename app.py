import streamlit as st
import pytesseract
from PIL import Image
import google.generativeai as genai
import json
import gspread
import time
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN ---
import os
if os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
UMBRAL_CONFIANZA = 80
ID_HOJA = st.secrets["ID_HOJA"]
modelo = genai.GenerativeModel("gemini-flash-lite-latest")

# --- FUNCIÓN: procesar una imagen ya abierta ---
def procesar(imagen):
    texto_ocr = pytesseract.image_to_string(imagen, lang="spa")
    prompt = f"""
Eres un asistente que extrae datos de comprobantes de pago peruanos (facturas y boletas).
Te daré el texto crudo obtenido por OCR. Devuelve ÚNICAMENTE un objeto JSON con estos campos:
- ruc_emisor, razon_social, tipo_comprobante, serie, numero, fecha_emision (AAAA-MM-DD),
  subtotal (número), igv (número), total (número), confianza (0 a 100).
Reglas: si un campo no se identifica con certeza, null. No inventes datos. Solo el JSON.

Texto OCR:
\"\"\"
{texto_ocr}
\"\"\"
"""
    respuesta = modelo.generate_content(prompt)
    texto_json = respuesta.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(texto_json)

# --- FUNCIÓN: guardar en Sheets ---
def guardar_en_sheets(nombre, datos, estado):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file("credenciales.json", scopes=scopes)
    cliente = gspread.authorize(creds)
    hoja = cliente.open_by_key(ID_HOJA).sheet1
    if not hoja.get_all_values():
        hoja.append_row(["Archivo","RUC","Razon Social","Tipo","Serie","Numero",
                         "Fecha","Subtotal","IGV","Total","Confianza","Estado"])
    hoja.append_row([nombre, datos.get("ruc_emisor"), datos.get("razon_social"),
                     datos.get("tipo_comprobante"), datos.get("serie"), datos.get("numero"),
                     datos.get("fecha_emision"), datos.get("subtotal"), datos.get("igv"),
                     datos.get("total"), datos.get("confianza"), estado])

# ============ INTERFAZ ============
st.set_page_config(page_title="Sistema IPA Contable", page_icon="📄")
st.title("📄 Sistema de Automatización Inteligente de Documentación Contable")
st.caption("C & M Consulting & Advices E.I.R.L.")

archivo = st.file_uploader("Sube una factura o boleta", type=["png", "jpg", "jpeg"])

if archivo is not None:
    imagen = Image.open(archivo)
    col1, col2 = st.columns(2)
    with col1:
        st.image(imagen, caption=archivo.name, use_container_width=True)

    with col2:
        with st.spinner("Procesando con OCR + IA..."):
            inicio = time.time()
            datos = procesar(imagen)
            tiempo = round(time.time() - inicio, 1)

        confianza = datos.get("confianza", 0)
        estado = "APROBADO" if confianza >= UMBRAL_CONFIANZA else "REVISION HUMANA"

        st.subheader("Datos extraídos")
        st.write(f"**RUC:** {datos.get('ruc_emisor')}")
        st.write(f"**Razón social:** {datos.get('razon_social')}")
        st.write(f"**Comprobante:** {datos.get('tipo_comprobante')} {datos.get('serie')}-{datos.get('numero')}")
        st.write(f"**Fecha:** {datos.get('fecha_emision')}")
        st.write(f"**Subtotal:** {datos.get('subtotal')}")
        st.write(f"**IGV:** {datos.get('igv')}")
        st.write(f"**Total:** {datos.get('total')}")
        st.write(f"⏱️ Procesado en {tiempo} s")

        st.progress(int(confianza), text=f"Confianza: {confianza}%")

        if estado == "APROBADO":
            st.success(f"✅ APROBADO automáticamente (confianza {confianza}%)")
        else:
            st.warning(f"⚠️ REQUIERE REVISIÓN HUMANA (confianza {confianza}%)")

    if st.button("💾 Guardar en Google Sheets"):
        guardar_en_sheets(archivo.name, datos, estado)
        st.success("Guardado en Google Sheets correctamente.")