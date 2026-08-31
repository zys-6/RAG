import base64


def bytes2str(content: bytes) -> str:
    return base64.b64encode(content).decode("utf-8")


def str2bytes(content: str) -> bytes:
    return base64.b64decode(content.encode("utf-8"))


def replace_escape(text: str) -> str:
    for escape in ["\t", "\r", "\b", "\n", "\f"]:
        text = text.replace(escape, "\\"+escape)
    return text