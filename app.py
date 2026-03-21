"""
Tu Mejor CV - ATS Harvard CV Generator
Flask web application for collecting client information and generating
professional CVs in Word format compatible with ATS systems.
"""

import os
import json
import uuid
import logging
from pathlib import Path

import anthropic
from flask import (
    Flask,
    render_template,
    request,
    send_file,
    flash,
    redirect,
    url_for,
    jsonify,
)
from dotenv import load_dotenv

from claude_processor import process_cv_with_claude, extract_contact_from_file
from cv_generator import generate_cv_docx

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24).hex())

UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "webp"}
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")) * 1024 * 1024

app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[1].lower()
    return "pdf" if ext == "pdf" else "image"


def get_anthropic_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no está configurada en las variables de entorno.")
    return anthropic.Anthropic(api_key=api_key)


def save_uploaded_file(file_obj) -> tuple[str, str]:
    """Save an uploaded file and return (file_path, file_type)."""
    file_extension = file_obj.filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
    file_path = str(UPLOAD_FOLDER / unique_filename)
    file_obj.save(file_path)
    return file_path, get_file_type(file_obj.filename)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/extraer-contacto", methods=["POST"])
def extraer_contacto():
    """
    Fast endpoint: receives an uploaded file, extracts only contact fields
    using Haiku, and returns them as JSON for auto-filling the form.
    """
    uploaded_file = request.files.get("archivo")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"success": False, "error": "No se recibió ningún archivo."}), 400

    if not allowed_file(uploaded_file.filename):
        return jsonify({"success": False, "error": "Formato de archivo no permitido."}), 400

    file_path, file_type = save_uploaded_file(uploaded_file)
    try:
        client = get_anthropic_client()
        contact_data = extract_contact_from_file(client, file_path, file_type)
        return jsonify({"success": True, "contacto": contact_data})
    except Exception as e:
        logger.error("Contact extraction error: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if Path(file_path).exists():
            Path(file_path).unlink(missing_ok=True)


@app.route("/generar", methods=["POST"])
def generar_cv():
    """
    Main endpoint: receives form data + optional file, calls Claude,
    generates DOCX, and returns it as a download.
    Supports file-only mode (no manual text required when a file is uploaded).
    """
    # ── Collect text input ────────────────────────────────────
    nombre = request.form.get("nombre", "").strip()
    telefono = request.form.get("telefono", "").strip()
    correo = request.form.get("correo", "").strip()
    direccion = request.form.get("direccion", "").strip()
    dni = request.form.get("dni", "").strip()
    licencia = request.form.get("licencia", "").strip()
    experiencia_texto = request.form.get("experiencia_texto", "").strip()
    formacion_texto = request.form.get("formacion_texto", "").strip()
    habilidades_texto = request.form.get("habilidades_texto", "").strip()
    info_adicional = request.form.get("info_adicional", "").strip()

    # Build structured text (only from fields the user actually filled in)
    text_parts = []
    if nombre:
        text_parts.append(f"Nombre completo: {nombre}")
    if telefono:
        text_parts.append(f"Telefono: {telefono}")
    if correo:
        text_parts.append(f"Correo electronico: {correo}")
    if direccion:
        text_parts.append(f"Direccion: {direccion}")
    if dni:
        text_parts.append(f"DNI: {dni}")
    if licencia:
        text_parts.append(f"Licencia de conducir: {licencia}")
    if experiencia_texto:
        text_parts.append(f"\nEXPERIENCIA LABORAL:\n{experiencia_texto}")
    if formacion_texto:
        text_parts.append(f"\nFORMACION ACADEMICA:\n{formacion_texto}")
    if habilidades_texto:
        text_parts.append(f"\nHABILIDADES Y COMPETENCIAS:\n{habilidades_texto}")
    if info_adicional:
        text_parts.append(f"\nINFORMACION ADICIONAL:\n{info_adicional}")

    text_input = "\n".join(text_parts)

    # ── Handle file upload ────────────────────────────────────
    file_path = ""
    file_type = ""
    uploaded_file = request.files.get("archivo")

    if uploaded_file and uploaded_file.filename:
        if not allowed_file(uploaded_file.filename):
            flash("Formato de archivo no permitido. Use PDF, PNG, JPG, JPEG, GIF o WEBP.", "error")
            return redirect(url_for("index"))
        file_path, file_type = save_uploaded_file(uploaded_file)

    # Require either a file OR some text (file-only mode is valid)
    if not text_input and not file_path:
        flash("Por favor, sube tu CV como archivo o completa al menos el campo de nombre.", "error")
        return redirect(url_for("index"))

    try:
        client = get_anthropic_client()
        logger.info("Processing CV — name: '%s', file: %s", nombre or "(from file)", bool(file_path))

        cv_data = process_cv_with_claude(
            client=client,
            text_input=text_input,
            file_path=file_path,
            file_type=file_type,
        )

        # Use name from extracted cv_data if the form field was empty
        candidate_name = nombre or cv_data.get("contacto", {}).get("nombre", "CV")
        safe_name = candidate_name.replace(" ", "_").replace("/", "-")
        download_name = f"CV_ATS_{safe_name}.docx"

        docx_buffer = generate_cv_docx(cv_data)

        return send_file(
            docx_buffer,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=download_name,
        )

    except ValueError as e:
        logger.error("Configuration error: %s", e)
        flash(str(e), "error")
        return redirect(url_for("index"))
    except json.JSONDecodeError as e:
        logger.error("JSON parsing error from Claude: %s", e)
        flash("Error al procesar la respuesta de la IA. Intenta de nuevo.", "error")
        return redirect(url_for("index"))
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        flash(f"Error inesperado: {str(e)}", "error")
        return redirect(url_for("index"))
    finally:
        if file_path and Path(file_path).exists():
            Path(file_path).unlink(missing_ok=True)


@app.errorhandler(413)
def too_large(e):
    flash(
        f"El archivo es demasiado grande. El tamaño máximo permitido es "
        f"{os.getenv('MAX_UPLOAD_SIZE_MB', '10')} MB.",
        "error",
    )
    return redirect(url_for("index"))


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=5000)
