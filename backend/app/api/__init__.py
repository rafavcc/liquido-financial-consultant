from pydantic import ValidationError

_MESSAGES = {
    "missing": "campo obrigatório",
    "decimal_parsing": "número inválido",
    "decimal_type": "número inválido",
    "decimal_max_digits": "número inválido",
    "decimal_max_places": "número inválido",
    "decimal_whole_digits": "número inválido",
    "float_parsing": "número inválido",
    "float_type": "número inválido",
    "date_parsing": "data inválida",
    "date_type": "data inválida",
    "date_from_datetime_parsing": "data inválida",
    "date_from_datetime_inexact": "data inválida",
    "enum": "valor inválido",
    "literal_error": "valor inválido",
    "int_parsing": "número inteiro inválido",
    "int_type": "número inteiro inválido",
    "int_from_float": "número inteiro inválido",
    "bool_parsing": "valor inválido",
    "bool_type": "valor inválido",
    "string_type": "texto inválido",
    "json_invalid": "JSON inválido",
}
_LIMITS = {
    "greater_than": ("deve ser maior que", "gt"),
    "greater_than_equal": ("deve ser maior ou igual a", "ge"),
    "less_than": ("deve ser menor que", "lt"),
    "less_than_equal": ("deve ser menor ou igual a", "le"),
}


def clean_message(msg: str) -> str:
    return msg.removeprefix("Value error, ")


def _message(error: dict) -> str:
    kind = error.get("type", "")
    if kind == "value_error":  # mensagens pt-BR escritas nos validadores
        return clean_message(error["msg"])
    if kind in _LIMITS:
        texto, chave = _LIMITS[kind]
        limite = (error.get("ctx") or {}).get(chave)
        return f"{texto} {limite}" if limite is not None else "valor inválido"
    return _MESSAGES.get(kind, "valor inválido")


def format_errors(errors: list[dict], skip_body: bool = True) -> list[str]:
    out = []
    for e in errors:
        loc = [str(x) for x in e.get("loc", ()) if not (skip_body and x == "body")]
        msg = _message(e)
        out.append(f"{'.'.join(loc)}: {msg}" if loc else msg)
    return out


def validation_messages(exc: ValidationError) -> list[str]:
    return format_errors(exc.errors(include_url=False), skip_body=False)
