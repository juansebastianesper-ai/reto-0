# Notas privadas

Aplicación web en Python (Flask + SQLite) para crear notas privadas con etiquetas y búsqueda, con registro e inicio de sesión.

## Características

- Registro e inicio de sesión con contraseñas cifradas (`werkzeug`).
- Cada usuario solo ve, edita y elimina **sus propias notas**.
- Creación, edición y eliminación de notas.
- Etiquetas por usuario, separadas por comas.
- Búsqueda por título, contenido y etiquetas.
- Filtro por etiqueta concreta.
- Interfaz responsive en español.

## Instalación

Necesitas Python 3.9 o superior.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Ejecución

En PowerShell:

```powershell
$env:SECRET_KEY = "cambia-esta-clave-por-una-larga-y-aleatoria"
python app.py
```

También puedes usar el CLI de Flask:

```powershell
flask --app app run
```

Abre <http://127.0.0.1:5000>.

La base de datos se crea automáticamente en `notes.db` la primera vez que se ejecuta la aplicación.

## Variables de entorno

| Variable      | Descripción                                      | Por defecto        |
|---------------|--------------------------------------------------|--------------------|
| `SECRET_KEY`  | Clave para firmar las sesiones. **Usar en producción.** | Valor aleatorio temporal |
| `DATABASE`    | Ruta al archivo SQLite.                          | `./notes.db`       |
| `FLASK_DEBUG` | Poner `1` para activar el modo depuración.        | Desactivado        |

## Notas de seguridad

- Las contraseñas nunca se guardan en texto plano.
- Las sesiones se almacenan en cookies firmadas.
- Las consultas de notas siempre filtran por el usuario autenticado.
- Para producción, usa una `SECRET_KEY` fija y secreta, desactiva el debug y sirve la app mediante un servidor WSGI detrás de HTTPS.
