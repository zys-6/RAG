import os
import traceback

from api.services.cajparser import CAJParser
from api.services.pdf import process_pdf
from api.services.utils import insert_fragments_into_milvus, requests_update_file


def process_caj(file_path: str, output: str, file_name: str, file_id: str, package_id: str, md5: str):

    try:
        caj = CAJParser(file_path)
        if output is None:
            if file_path.endswith(".caj"):
                output = file_path.replace(".caj", ".pdf")
            elif (len(file_path) > 4 and (file_path[-4] == '.' or file_path[-3] == '.') and not file_path.endswith(
                    ".pdf")):
                output = os.path.splitext(file_path)[0] + ".pdf"
            else:
                output = file_path + ".pdf"
        caj.convert(output)
        print('caj type', caj.format, flush=True)
        with open(output, 'rb') as fin:
            _content = fin.read()
            fragments = process_pdf(_content, True, file_name, file_id, package_id, md5)
        return fragments
    except Exception as e:
        print(e)
        traceback.print_exc()
        requests_update_file(file_id, package_id, "failed")
