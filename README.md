# Tu Mejor CV — Generador ATS Harvard

Aplicacion web que transforma informacion del candidato en un CV profesional en formato Word,
optimizado para sistemas ATS (Applicant Tracking System) estilo Harvard, usando Claude AI.

## Caracteristicas

- Formulario web para ingresar datos del candidato
- Carga de archivos: CV existente en **PDF** o **imagen** (PNG, JPG, etc.)
- IA (Claude Opus) extrae, organiza y optimiza todo el contenido
- Genera archivo **.docx** listo para descargar
- Formato ATS Harvard: sin graficos, tablas ni columnas

## Estructura del CV generado

1. Informacion de contacto (nombre, telefono, correo, direccion, DNI, licencia)
2. Perfil profesional (parrafo en primera persona tacita, max. 5 lineas)
3. Experiencia laboral (mas reciente primero, funciones en infinitivo, logro con indicador %)
4. Software e idiomas (si hay datos)
5. Formacion academica (descendente)
6. Habilidades tecnicas
7. Competencias blandas

## Instalacion

```bash
pip install -r requirements.txt
cp .env.example .env
# Edita .env y agrega tu ANTHROPIC_API_KEY
```

## Uso

```bash
python app.py
```

Abre http://localhost:5000 en tu navegador.

## Variables de entorno

| Variable | Descripcion | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | API key de Anthropic (requerida) | - |
| `FLASK_SECRET_KEY` | Clave secreta para Flask sessions | aleatorio |
| `FLASK_DEBUG` | Modo debug | false |
| `MAX_UPLOAD_SIZE_MB` | Tamano maximo de archivo subido | 10 |
