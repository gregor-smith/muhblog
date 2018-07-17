from datetime import datetime

from flask import Blueprint

blueprint = Blueprint(name='filters', import_name=__name__)


@blueprint.app_template_filter()
def format_datetime(dt: datetime) -> str:
    return f'{dt:%d/%m/%Y %H:%M}'


@blueprint.app_template_filter()
def format_datetime_iso(dt: datetime) -> str:
    return f'{dt:%Y-%m-%d %H:%M:%S}'
