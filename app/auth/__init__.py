from flask import Blueprint

auth_bp = Blueprint(
    "auth", __name__, url_prefix=""  # ➜ blueprint **name**  # no prefix needed
)

from . import routes
