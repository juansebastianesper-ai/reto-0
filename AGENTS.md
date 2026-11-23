# AGENTS.md

## Proyecto
Aplicación web para crear notas privadas con etiquetas, búsqueda e inicio de sesión.
Cada usuario gestiona solo sus notas; contraseñas con hash y SECRET_KEY desde entorno.

## Stack
Python 3.9+, Flask 3.x, SQLite, Jinja2, Werkzeug, python-dotenv, CSS vanilla.

## Comandos
Instalar: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Ejecutar: .\.venv\Scripts\python.exe app.py (requiere SECRET_KEY en .env o entorno).
Pruebas: python -m pytest -v
Estilo: ruff check .

## Estructura
app.py: rutas, validación, acceso a datos, auth y búsqueda; toda la lógica.
templates/: plantillas Jinja2 de la interfaz en español.
templates/base.html: layout, navegación, mensajes flash y enlace al CSS.
templates/login.html, register.html: formularios de inicio de sesión y registro.
templates/notes.html: listado, buscador, etiquetas y tarjetas de notas.
templates/note_form.html, note_detail.html: formulario de nota y vista completa.
static/: recursos estáticos.
static/style.css: estilos, componentes y diseño responsive.
requirements.txt: dependencias Flask y python-dotenv.
.env.example: nombres de variables sin valores reales.
.gitignore: ignora entorno, cachés, notes.db y .env.
README.md: instalación, ejecución y notas de seguridad.
notes.db: SQLite generada con usuarios, notas y etiquetas.
.venv/, __pycache__/, .git/: entorno, bytecode e historial; no editar a mano.

## Qué no hacer
- No modificar las pruebas para que pasen.
- No escribir claves en el código; usar variables de entorno.
- No instalar dependencias sin explicar para qué.
- No hacer commit ni push.

## Lecciones aprendidas
- pytest debe estar en requirements.txt y la suite debe pasar antes de cada commit.
- SECRET_KEY se lee siempre de una variable de entorno; nunca se genera en el código.
- El contenido de una nota se valida con un máximo explícito; MAX_CONTENT_LENGTH no basta.
