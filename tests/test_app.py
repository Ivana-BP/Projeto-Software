import pytest

from app import app, db


@pytest.fixture
def client():
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False
    )

    with app.app_context():
        db.create_all()

        with app.test_client() as client:
            yield client

        db.session.remove()
        db.drop_all()


def test_pagina_inicial(client):
    resposta = client.get("/")
    assert resposta.status_code == 200


def test_pagina_login(client):
    resposta = client.get("/entrar")
    assert resposta.status_code in (200, 302)


def test_pagina_cadastro(client):
    resposta = client.get("/cadastro")
    assert resposta.status_code == 200


def test_tarefas_exige_login(client):
    resposta = client.get("/tarefas")
    assert resposta.status_code == 302