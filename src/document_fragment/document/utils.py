import io
import logging
import re

from PIL import Image

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def crop_image(content, l=None, r=None, t=None, b=None):
    """这个地方很奇怪，必须使用文件读写才不报错"""
    try:
        img = Image.open(io.BytesIO(content))
    except Exception as e:
        logger.error("crop_image error: {}".format(e))
        return None
    width, height = img.size
    try:
        if l:
            l = width * int(l) / 100000
        else:
            l = 0
        if r:
            r = width - width * int(r) / 100000
        else:
            r = width
        if t:
            t = height * int(t) / 100000
        else:
            t = 0
        if b:
            b = height - height * int(b) / 100000
        else:
            b = height
    except Exception as e:
        logger.error("crop_image error: {}".format(e))
        return content
    cropped = img.crop((l, t, r, b))
    buffer = io.BytesIO()
    try:
        cropped.save(buffer, format="PNG")
    except Exception as e:
        logger.warning("crop_image: " + str(e))
        cropped.convert("RGB").save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.read()


def add_namespaces_into(xml, namespaces, key):
    if key in xml:
        xml = xml.replace(key, key + " " + " ".join(namespaces) + " ")
    elif key[:-1] + ">" in xml:
        xml = xml.replace(key[:-1] + ">", key + " " + " ".join(namespaces) + " >")
    else:
        raise ValueError(xml, namespaces, key)
    return xml


def add_namespaces_onto(xml, namespaces, tag):
    _tag = tag + " ".join(namespaces) + " >"
    return _tag + xml + tag.replace("<", "</") + ">"


def get_val_from_dom(dom, tag_name, attribute_name):
    tags = dom.getElementsByTagName(tag_name)
    if tags:
        if attribute_name:
            return tags[0].getAttribute(attribute_name)
        else:
            return True
    if attribute_name:
        return None
    else:
        return False


def get_text_from_run_dom(dom):
    ret = ""
    for w_t in dom.getElementsByTagName("w:t"):
        if hasattr(w_t, "childNodes"):
            for child_node in w_t.childNodes:
                if hasattr(child_node, "data"):
                    ret += child_node.data
    return ret


def get_text_from_dom(dom):
    ret = ""
    for w_t in dom.getElementsByTagName("w:t"):
        if hasattr(w_t, "childNodes"):
            for child_node in w_t.childNodes:
                if hasattr(child_node, "data"):
                    ret += child_node.data
    return ret


def get_crop_shape(imagedata_dom):
    l = imagedata_dom.getAttribute("cropleft")
    r = imagedata_dom.getAttribute("cropright")
    t = imagedata_dom.getAttribute("croptop")
    b = imagedata_dom.getAttribute("cropbottom")
    l, r, t, b = l if l else None, r if r else None, t if t else None, b if b else None
    if l:
        if l.endswith("f"):
            l = str(int((int(l[:-1]) / 65536 * 100000)))
        else:
            l = str(int(float(l) * 100000))
    if r:
        if r.endswith("f"):
            r = str(int((int(r[:-1]) / 65536 * 100000)))
        else:
            r = str(int(float(r) * 100000))
    if t:
        if t.endswith("f"):
            t = str(int((int(t[:-1]) / 65536 * 100000)))
        else:
            t = str(int(float(t) * 100000))
    if b:
        if b.endswith("f"):
            b = str(int((int(b[:-1]) / 65536 * 100000)))
        else:
            b = str(int(float(b) * 100000))
    return l, r, t, b


def clean_wildcard(x, sp=None):
    sp = ".*?()[]+" if sp is None else sp
    return re.sub("(" + "|".join([f"\\{s}" for s in sp]) + ")", "\\\\\g<1>", x)