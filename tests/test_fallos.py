import os
import uuid
from pathlib import Path

import pytest

import app as app_module

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE", tmp_path / "test_fallos.db")
    app_module.init_db()
    app_module.app.config.update(TESTING=True)

    cliente = app_module.app.test_client()
    usuario = f"usuario_{uuid.uuid4().hex[:8]}"
    clave = "clave-segura-123"

    respuesta = cliente.post(
        "/register",
        data={"username": usuario, "password": clave, "confirm_password": clave},
    )
    assert respuesta.status_code == 302
    respuesta = cliente.post("/login", data={"username": usuario, "password": clave})
    assert respuesta.status_code == 302

    return cliente


def test_contenido_demasiado_largo_se_rechaza(cliente):
    contenido = "x" * 10001

    respuesta = cliente.post(
        "/notes/new",
        data={
            "title": "Nota con contenido enorme",
            "content": contenido,
            "tags": "",
        },
        follow_redirects=True,
    )
    html = respuesta.get_data(as_text=True)

    with app_module.app.app_context():
        total = app_module.get_db().execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    assert total == 0, "La nota se guardó: falta el límite de 10000 caracteres."

    assert "El contenido no puede superar los 10000 caracteres." in html


def test_la_suite_de_pruebas_esta_configurada():
    requirements = (RAIZ / "requirements.txt").read_text(encoding="utf-8")

    assert "pytest" in requirements.lower()
    assert (RAIZ / "tests" / "test_humo.py").is_file()
    assert (RAIZ / "tests" / "test_fallos.py").is_file()


def test_secret_key_se_lee_del_entorno():
    assert app_module.app.config["SECRET_KEY"] == os.environ["SECRET_KEY"]


def test_secret_key_no_tiene_fallback_aleatorio():
    fuente = (RAIZ / "app.py").read_text(encoding="utf-8")

    assert "secrets.token_hex" not in fuente
    assert 'os.environ["SECRET_KEY"]' in fuente
