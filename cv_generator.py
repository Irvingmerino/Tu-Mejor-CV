"""
Word document (DOCX) generator for ATS Harvard-style CVs.
"""

import io
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


# ── Color palette ──────────────────────────────────────────────
COLOR_BLACK = RGBColor(0x00, 0x00, 0x00)
COLOR_DARK_GRAY = RGBColor(0x33, 0x33, 0x33)

# ── Typography ─────────────────────────────────────────────────
FONT_NAME = "Calibri"
FONT_SIZE_NAME = 18
FONT_SIZE_CONTACT = 10
FONT_SIZE_SECTION = 12
FONT_SIZE_BODY = 11
FONT_SIZE_SMALL = 10


def _set_font(run, size: int, bold: bool = False, color: RGBColor = COLOR_BLACK):
    run.font.name = FONT_NAME
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


def _add_horizontal_rule(paragraph):
    """Add a thin bottom border to a paragraph (simulates a horizontal rule)."""
    p = paragraph._p
    pPr = p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_section_header(doc: Document, title: str):
    """Add a bold section header with an underline rule."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(title.upper())
    _set_font(run, FONT_SIZE_SECTION, bold=True)
    _add_horizontal_rule(p)


def _add_body_paragraph(doc: Document, text: str, space_after: int = 4) -> None:
    """Add a plain body paragraph."""
    p = doc.add_paragraph(text)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    for run in p.runs:
        _set_font(run, FONT_SIZE_BODY)


def _set_document_margins(doc: Document):
    """Set 2.5 cm margins on all sides."""
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)


def generate_cv_docx(cv_data: dict) -> io.BytesIO:
    """
    Generate an ATS Harvard-format CV as a Word document.
    Returns a BytesIO buffer containing the .docx file.
    """
    doc = Document()
    _set_document_margins(doc)

    # Remove default empty paragraph
    for para in doc.paragraphs:
        para._element.getparent().remove(para._element)

    contacto = cv_data.get("contacto", {})
    experiencia = cv_data.get("experiencia_laboral", [])
    software_idiomas = cv_data.get("software_idiomas", [])
    formacion = cv_data.get("formacion_academica", [])
    habilidades = cv_data.get("habilidades", [])
    competencias = cv_data.get("competencias", [])
    perfil = cv_data.get("perfil_profesional", "")

    # ── 1. NAME ───────────────────────────────────────────────
    nombre = contacto.get("nombre", "").strip()
    if nombre:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(nombre.upper())
        _set_font(run, FONT_SIZE_NAME, bold=True)

    # ── 2. CONTACT INFO ───────────────────────────────────────
    contact_parts = []
    if contacto.get("telefono"):
        contact_parts.append(contacto["telefono"])
    if contacto.get("correo"):
        contact_parts.append(contacto["correo"])
    if contacto.get("direccion"):
        contact_parts.append(contacto["direccion"])
    if contacto.get("dni"):
        contact_parts.append(f"DNI: {contacto['dni']}")
    if contacto.get("licencia"):
        contact_parts.append(f"Licencia: {contacto['licencia']}")

    if contact_parts:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(8)
        run = p.add_run("  |  ".join(contact_parts))
        _set_font(run, FONT_SIZE_CONTACT)

    # ── 3. PROFESSIONAL PROFILE ──────────────────────────────
    if perfil.strip():
        _add_section_header(doc, "Perfil Profesional")
        _add_body_paragraph(doc, perfil)

    # ── 4. WORK EXPERIENCE ───────────────────────────────────
    if experiencia:
        _add_section_header(doc, "Experiencia Laboral")
        for exp in experiencia:
            empresa = exp.get("empresa", "").strip()
            puesto = exp.get("puesto", "").strip()
            ubicacion = exp.get("ubicacion", "").strip()
            periodo = exp.get("periodo", "").strip()
            funciones = exp.get("funciones", [])
            logro = exp.get("logro_destacado", "").strip()

            # Company line: bold company | period
            if empresa or puesto:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(1)

                if puesto:
                    run_puesto = p.add_run(puesto)
                    _set_font(run_puesto, FONT_SIZE_BODY, bold=True)

                if empresa:
                    run_sep = p.add_run(" - " if puesto else "")
                    _set_font(run_sep, FONT_SIZE_BODY, bold=True)
                    run_empresa = p.add_run(empresa)
                    _set_font(run_empresa, FONT_SIZE_BODY, bold=True)

            # Location and period
            meta_parts = []
            if ubicacion:
                meta_parts.append(ubicacion)
            if periodo:
                meta_parts.append(periodo)
            if meta_parts:
                p2 = doc.add_paragraph("  |  ".join(meta_parts))
                p2.paragraph_format.space_before = Pt(0)
                p2.paragraph_format.space_after = Pt(2)
                for run in p2.runs:
                    _set_font(run, FONT_SIZE_SMALL, color=COLOR_DARK_GRAY)

            # Functions
            for funcion in funciones:
                if funcion.strip():
                    p3 = doc.add_paragraph()
                    p3.paragraph_format.space_before = Pt(0)
                    p3.paragraph_format.space_after = Pt(1)
                    p3.paragraph_format.left_indent = Cm(0.5)
                    run = p3.add_run(f"- {funcion.strip()}")
                    _set_font(run, FONT_SIZE_BODY)

            # Achievement
            if logro:
                p4 = doc.add_paragraph()
                p4.paragraph_format.space_before = Pt(3)
                p4.paragraph_format.space_after = Pt(2)
                p4.paragraph_format.left_indent = Cm(0.5)
                run_label = p4.add_run("Logro destacado: ")
                _set_font(run_label, FONT_SIZE_BODY, bold=True)
                run_logro = p4.add_run(logro)
                _set_font(run_logro, FONT_SIZE_BODY)

    # ── 5. SOFTWARE & LANGUAGES ──────────────────────────────
    si_filtered = [s for s in software_idiomas if s.get("nombre", "").strip()]
    if si_filtered:
        _add_section_header(doc, "Software e Idiomas")
        for item in si_filtered:
            nombre_item = item.get("nombre", "").strip()
            nivel = item.get("nivel", "").strip()
            cert = item.get("certificacion", "").strip()

            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(2)

            run_nombre = p.add_run(nombre_item)
            _set_font(run_nombre, FONT_SIZE_BODY, bold=True)

            details = []
            if nivel:
                details.append(nivel)
            if cert:
                details.append(f"Certificacion: {cert}")
            if details:
                run_detail = p.add_run(" - " + " | ".join(details))
                _set_font(run_detail, FONT_SIZE_BODY)

    # ── 6. EDUCATION ─────────────────────────────────────────
    if formacion:
        _add_section_header(doc, "Formacion Academica")
        for edu in formacion:
            institucion = edu.get("institucion", "").strip()
            carrera = edu.get("carrera", "").strip()
            fechas = edu.get("fechas", "").strip()

            if not (institucion or carrera):
                continue

            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(1)

            if carrera:
                run_carrera = p.add_run(carrera)
                _set_font(run_carrera, FONT_SIZE_BODY, bold=True)

            if institucion:
                sep = " - " if carrera else ""
                run_inst = p.add_run(sep + institucion)
                _set_font(run_inst, FONT_SIZE_BODY)

            if fechas:
                p2 = doc.add_paragraph(fechas)
                p2.paragraph_format.space_before = Pt(0)
                p2.paragraph_format.space_after = Pt(2)
                for run in p2.runs:
                    _set_font(run, FONT_SIZE_SMALL, color=COLOR_DARK_GRAY)

    # ── 7. SKILLS (HARD) ─────────────────────────────────────
    hab_filtered = [h for h in habilidades if h.strip()]
    if hab_filtered:
        _add_section_header(doc, "Habilidades")
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run("  -  ".join(hab_filtered))
        _set_font(run, FONT_SIZE_BODY)

    # ── 8. COMPETENCIES (SOFT) ───────────────────────────────
    comp_filtered = [c for c in competencias if c.strip()]
    if comp_filtered:
        _add_section_header(doc, "Competencias")
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run("  -  ".join(comp_filtered))
        _set_font(run, FONT_SIZE_BODY)

    # ── Save to buffer ────────────────────────────────────────
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
