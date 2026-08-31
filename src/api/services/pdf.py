import traceback

import tasks.main as tasks
from api.services.utils import insert_fragments_into_milvus, requests_update_file


@insert_fragments_into_milvus
def process_pdf(file_content: bytes, sync: bool, file_name: str, file_id: str, package_id: str, md5: str):
    try:
        if sync:
            resp = tasks.process_pdf_core(file_content, None)
            resp = [fragment.to_json() for fragment in resp]
        else:
            raise NotImplementedError('Not implemented')
        return resp
    except Exception as e:
        print(e)
        traceback.print_exc()
        requests_update_file(file_id, package_id, "failed")
