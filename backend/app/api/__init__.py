
from pydantic import ValidationError


def clean_message(msg: str) -> str:
    return msg.removeprefix("Value error, ")


def format_errors(errors: list[dict], skip_body: bool = True) -> list[str]:
    out = []
    for e in errors:
        loc = [str(x) for x in e.get("loc", ()) if not (skip_body and x == "body")]
        msg = clean_message(e["msg"])
        out.append(f"{'.'.join(loc)}: {msg}" if loc else msg)
    return out


def validation_messages(exc: ValidationError) -> list[str]:
    return format_errors(exc.errors(include_url=False, include_context=False), skip_body=False)


__all__ = ["format_errors", "validation_messages"]
