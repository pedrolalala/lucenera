"""Função auxiliar para registrar blueprints adicionais sem alterar main.py."""
from __future__ import annotations

from flask import Flask

from routes.teams_webhook import teams_bp


def registrar_blueprints(app: Flask) -> None:
    """Registra os blueprints externos utilizados pelas integrações."""

    app.register_blueprint(teams_bp)
