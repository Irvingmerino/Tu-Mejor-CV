"""
Claude API integration for CV data extraction and enhancement.
"""

import base64
import json
import re
import anthropic
import pdfplumber

SYSTEM_PROMPT = """Eres un experto redactor de CVs profesionales con especialización en formatos ATS (Applicant Tracking System) estilo Harvard. Tu tarea es extraer, organizar y optimizar la información del candidato para producir un CV de alta calidad y completamente compatible con sistemas ATS.

Reglas absolutas:
- Responde SIEMPRE en español
- Devuelve ÚNICAMENTE un objeto JSON válido, sin texto adicional, sin markdown, sin bloques de código
- No uses íconos, viñetas especiales, emojis ni caracteres no estándar
- Todo el texto debe estar listo para usar directamente
- Usa solo caracteres UTF-8 estándar"""

EXTRACTION_PROMPT = """A partir de la información proporcionada, extrae y organiza todos los datos del candidato para construir un CV en formato ATS estilo Harvard.

Sigue estrictamente estos estándares:

1. INFORMACIÓN DE CONTACTO: Nombres completos, teléfono, correo, dirección, DNI (si aplica), licencia de conducir (si aplica).

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


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text content from a PDF file."""
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def encode_image_base64(file_path: str) -> tuple[str, str]:
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
    messages = []

    if file_path and file_type == "pdf":
        pdf_text = extract_text_from_pdf(file_path)
        combined_text = f"{text_input}\n\nContenido del PDF:\n{pdf_text}".strip()
        messages.append({
            "role": "user",
            "content": f"{EXTRACTION_PROMPT}\n\nInformación del candidato:\n{combined_text}"
        })

    elif file_path and file_type in ("image", "jpg", "jpeg", "png", "gif", "webp"):
        image_data, media_type = encode_image_base64(file_path)
        content = []
        if text_input.strip():
            content.append({
                "type": "text",
                "text": f"{EXTRACTION_PROMPT}\n\nInformación adicional del candidato:\n{text_input}"
            })
        else:
            content.append({
                "type": "text",
                "text": EXTRACTION_PROMPT
            })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_data,
            }
        })
        messages.append({"role": "user", "content": content})

    else:
        messages.append({
            "role": "user",
            "content": f"{EXTRACTION_PROMPT}\n\nInformación del candidato:\n{text_input}"
        })

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    raw_text = response.content[0].text.strip()

    # Remove markdown code blocks if present
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)

    cv_data = json.loads(raw_text)
    return cv_data
