"""
Claude API integration for CV data extraction and enhancement.
"""

import base64
import io
import json
import re
import logging

import anthropic
import pdfplumber
import pypdfium2

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un experto redactor de CVs profesionales con especialización en formatos ATS (Applicant Tracking System) estilo Harvard. Tu tarea es extraer, organizar y optimizar la información del candidato para producir un CV de alta calidad y completamente compatible con sistemas ATS.

Reglas absolutas:
- Responde SIEMPRE en español
- Devuelve ÚNICAMENTE un objeto JSON válido, sin texto adicional, sin markdown, sin bloques de código
- No uses íconos, viñetas especiales, emojis ni caracteres no estándar
- Todo el texto debe estar listo para usar directamente
- Usa solo caracteres UTF-8 estándar"""

EXTRACTION_PROMPT = """Extrae y organiza TODOS los datos del candidato disponibles en la fuente proporcionada (documento adjunto y/o información textual) para construir un CV completo en formato ATS estilo Harvard.

IMPORTANTE: Si se adjunta un documento (PDF o imagen), ese documento es la fuente primaria de información. Extrae absolutamente todo lo que contenga: datos de contacto, experiencia laboral, formación, habilidades, logros, fechas, empresas, cargos, etc. No omitas ningún dato presente en el documento.

Sigue estrictamente estos estándares:

1. INFORMACIÓN DE CONTACTO: Extraer del documento todos los datos disponibles — nombres completos, teléfono, correo, dirección, DNI (si aplica), licencia de conducir (si aplica). Si hay información textual adicional que complementa o corrige estos datos, úsala con prioridad.

2. PERFIL PROFESIONAL: Párrafo breve (máximo 5 líneas) en primera persona tácita (sin "yo soy"). Integra: experiencia destacada, formación académica relevante, principales habilidades técnicas y blandas, y propuesta de valor profesional alineada al mercado. Usa lenguaje dinámico y orientado a resultados.

3. EXPERIENCIA LABORAL: Ordenada de más reciente a más antigua. Por cada cargo:
   - Nombre de empresa, puesto, ubicación, periodo (formato: "febrero 2023 - diciembre 2024")
   - Funciones con verbos en infinitivo (coordinar, supervisar, liderar, gestionar, etc.)
   - Logro destacado en primera persona con indicador porcentual real o estimado
   Optimiza con palabras clave del sector profesional del candidato.

4. SOFTWARE E IDIOMAS: Solo si hay datos disponibles. Herramienta, nivel de manejo, certificaciones.

5. FORMACIÓN ACADÉMICA: Institución, carrera/curso, fechas (si disponibles). Incluye cursos, diplomados, capacitaciones en orden cronológico descendente.

6. HABILIDADES: Listar habilidades técnicas (duras) que el candidato domina con solidez.

7. COMPETENCIAS: Redactar competencias blandas o profesionales observables en el desempeño.

Devuelve ÚNICAMENTE el siguiente JSON con toda la información extraída y optimizada:

{
  "contacto": {
    "nombre": "",
    "telefono": "",
    "correo": "",
    "direccion": "",
    "dni": "",
    "licencia": ""
  },
  "perfil_profesional": "",
  "experiencia_laboral": [
    {
      "empresa": "",
      "puesto": "",
      "ubicacion": "",
      "periodo": "",
      "funciones": ["", ""],
      "logro_destacado": ""
    }
  ],
  "software_idiomas": [
    {
      "nombre": "",
      "nivel": "",
      "certificacion": ""
    }
  ],
  "formacion_academica": [
    {
      "institucion": "",
      "carrera": "",
      "fechas": ""
    }
  ],
  "habilidades": ["", ""],
  "competencias": ["", ""]
}

Si algún campo no tiene información disponible, usa cadena vacía "" para strings o lista vacía [] para arrays. No inventes datos que no estén en la fuente."""

CONTACT_EXTRACTION_PROMPT = """Extrae ÚNICAMENTE los datos de contacto del candidato del documento adjunto.

Devuelve SOLO este JSON (sin texto adicional, sin markdown):
{
  "nombre": "",
  "telefono": "",
  "correo": "",
  "direccion": "",
  "dni": "",
  "licencia": ""
}

Reglas:
- Extrae exactamente lo que aparece en el documento, sin inventar ni completar datos
- Si un campo no está presente, usa cadena vacía ""
- nombre: nombres y apellidos completos
- telefono: número con código de país si está disponible
- correo: dirección de email
- direccion: dirección física o ciudad/país
- dni: número de documento de identidad (DNI, CE, pasaporte, etc.)
- licencia: tipo y categoría de licencia de conducir si aparece"""


# ── PDF utilities ──────────────────────────────────────────────

def _try_extract_pdf_text(file_path: str) -> str:
    """
    Attempt to extract text from a PDF with pdfplumber.
    Returns empty string on failure or if the PDF is image-based.
    """
    try:
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts).strip()
    except Exception as exc:
        logger.debug("pdfplumber could not extract text: %s", exc)
        return ""


def _pdf_to_images_base64(file_path: str, max_pages: int = 4) -> list[tuple[str, str]]:
    """
    Render each PDF page to a PNG image using pypdfium2.
    Returns a list of (base64_data, media_type) tuples.
    """
    results = []
    try:
        pdf = pypdfium2.PdfDocument(file_path)
        num_pages = min(len(pdf), max_pages)
        for i in range(num_pages):
            page = pdf[i]
            bitmap = page.render(scale=2.0)          # 2× scale for legibility
            pil_img = bitmap.to_pil()
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            buf.seek(0)
            b64 = base64.standard_b64encode(buf.read()).decode("utf-8")
            results.append((b64, "image/png"))
    except Exception as exc:
        logger.error("PDF-to-image rendering failed: %s", exc)
        raise RuntimeError(
            f"No se pudo procesar el archivo PDF. "
            f"Asegurate de que el archivo no este corrupto o protegido con contraseña."
        ) from exc
    return results


# ── Image utilities ────────────────────────────────────────────

def _encode_image_base64(file_path: str) -> tuple[str, str]:
    """Encode an image file to base64 and detect its media type."""
    extension = file_path.rsplit(".", 1)[-1].lower()
    media_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    media_type = media_type_map.get(extension, "image/jpeg")
    with open(file_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")
    return image_data, media_type


# ── Message builders ───────────────────────────────────────────

def _image_block(b64_data: str, media_type: str) -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": b64_data},
    }


def _build_messages_for_file(
    prompt: str,
    file_path: str,
    file_type: str,
    extra_text: str = "",
) -> list[dict]:
    """
    Build the Claude messages list for a given file.

    Strategy:
    - Text-based PDF  → extract text, send as a text block
    - Scanned/image PDF → render pages with pypdfium2, send as image blocks
    - Image file       → send directly as an image block
    """
    text_header = prompt
    if extra_text.strip():
        text_header = f"{prompt}\n\nInformación adicional del candidato:\n{extra_text}"

    if file_type == "pdf":
        pdf_text = _try_extract_pdf_text(file_path)

        if pdf_text:
            # Text-based PDF: no vision needed
            logger.debug("PDF text extraction successful (%d chars)", len(pdf_text))
            full_text = f"{text_header}\n\nContenido del documento:\n{pdf_text}"
            return [{"role": "user", "content": full_text}]
        else:
            # Image-based (scanned) PDF: render to images
            logger.debug("PDF has no extractable text — rendering pages as images")
            images = _pdf_to_images_base64(file_path)
            content = [{"type": "text", "text": text_header}]
            content += [_image_block(b64, mt) for b64, mt in images]
            return [{"role": "user", "content": content}]

    else:
        # Plain image file
        b64, media_type = _encode_image_base64(file_path)
        content = [
            {"type": "text", "text": text_header},
            _image_block(b64, media_type),
        ]
        return [{"role": "user", "content": content}]


# ── JSON helper ────────────────────────────────────────────────

def _parse_json_response(raw_text: str) -> dict:
    """Strip markdown fences and parse JSON."""
    raw_text = raw_text.strip()
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)
    return json.loads(raw_text)


# ── Public API ─────────────────────────────────────────────────

def extract_contact_from_file(
    client: anthropic.Anthropic,
    file_path: str,
    file_type: str,
) -> dict:
    """
    Fast contact-only extraction from a file using Haiku model.
    Returns a dict with: nombre, telefono, correo, direccion, dni, licencia.
    """
    messages = _build_messages_for_file(CONTACT_EXTRACTION_PROMPT, file_path, file_type)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=(
            "Eres un asistente que extrae datos de contacto de documentos. "
            "Responde SOLO con JSON válido, sin texto adicional."
        ),
        messages=messages,
    )
    return _parse_json_response(response.content[0].text)


def process_cv_with_claude(
    client: anthropic.Anthropic,
    text_input: str = "",
    file_path: str = "",
    file_type: str = "",
) -> dict:
    """
    Process CV data using Claude API.
    Returns structured CV data as a dictionary.
    """
    if file_path:
        messages = _build_messages_for_file(EXTRACTION_PROMPT, file_path, file_type, text_input)
    else:
        messages = [{
            "role": "user",
            "content": f"{EXTRACTION_PROMPT}\n\nInformación del candidato:\n{text_input}",
        }]

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return _parse_json_response(response.content[0].text)
