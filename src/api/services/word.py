import json
import os
import time
import traceback
import uuid
from pathlib import Path

import tasks.main as tasks
from api.services.utils import insert_fragments_into_milvus, requests_update_file
from utils.utils import get_hash_code


@insert_fragments_into_milvus
def process_word(file_content: bytes, sync, file_name: str, file_id: str, package_id: str, md5: str):
    try:
        if sync:
            resp = tasks.process_word_core(file_content)
            resp = [fragment.to_json() for fragment in resp]
        else:
            tasks.process_word.delay(file_content)
            resp = get_hash_code(file_content)
        return resp
    except Exception as e:
        print(e)
        traceback.print_exc()
        requests_update_file(file_id, package_id, "failed")



def get_async_result(hash_code: str):
    result = redis_client.hget("document_fragment_result", hash_code)
    if not result:
        raise KeyError(hash_code)
    return json.loads(result)


def convert_doc_to_docx(content: bytes) -> bytes:
    doc_filepath = Path(f"/tmp/{str(uuid.uuid1())}.doc")
    with open(doc_filepath, "wb") as fout:
        fout.write(content)

    os.system(f"unoconv -d document --format=docx {doc_filepath}")
    time.sleep(3)

    if doc_filepath.with_suffix(".docx").exists():
        with open(doc_filepath.with_suffix(".docx"), "rb") as fin:
            content = fin.read()
    doc_filepath.unlink(missing_ok=True)
    return content
