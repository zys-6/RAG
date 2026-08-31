import os
import hashlib
import traceback
import zipfile
from io import BytesIO
from pathlib import Path
from ftplib import FTP

from api.services.caj import process_caj
from api.services.manage import add_library_status
from api.services.pdf import process_pdf
from api.services.utils import requests_create_file, requests_update_file, create_file_uuid
from api.services.word import process_word
from rag.configs import app_config

FTP_HOST = app_config['FTP_HOST']
FTP_PORT = app_config['FTP_PORT']
FTP_USERNAME = app_config['FTP_USERNAME']
FTP_PASSWORD = app_config['FTP_PASSWORD']
TMP_DIR = Path("static/tmp")

if not TMP_DIR.exists():
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def filepath_generator(path: Path):
    if path.is_file() and path.suffix in (".pdf", ".doc", ".docx", ".caj"):
        yield path
    elif path.is_dir():
        for _path in path.iterdir():
            yield from filepath_generator(_path)


async def process_zip(content: bytes, package_id, user_id):
    file = zipfile.ZipFile(BytesIO(content))
    """统一解压缩到指定地点，然后进行遍历"""
    save_file_dir = Path(__file__).parent.parent / 'static' / 'file'
    tmp_dir = TMP_DIR / hashlib.md5(content).hexdigest()
    file.extractall(tmp_dir)
    fragments_dict = {}
    for filepath in filepath_generator(tmp_dir):
        with open(filepath, "rb") as _file:
            _content = _file.read()
            id = create_file_uuid()
            file_id = hashlib.md5(_content).hexdigest()
            with open(Path(save_file_dir, file_id + filepath.suffix), 'wb') as __file:
                __file.write(_content)
            requests_create_file(id=id, file_id=file_id, file_name=_content.filename, file_size=_content.__sizeof__() / 1024,
                                 file_path=str(file_id + '.' + filepath.suffix), file_type=filepath.suffix.replace('.',''),
                                 package_id=package_id, user_id=user_id)
            if filepath.suffix == '.caj':
                fragments_dict[str(filepath).replace(str(tmp_dir), "")] = process_caj(filepath, None, _content.filename, id, package_id)
            else:
                if filepath.suffix == '.pdf':
                    fragments_dict[str(filepath).replace(str(tmp_dir), "").encode('utf-8')] = process_pdf(_content, True, _content.filename, id, package_id)
                elif filepath.suffix in (".docx", ".doc"):
                    fragments_dict[str(filepath).replace(str(tmp_dir), "").encode('utf-8')] = process_word(_content, True, _content.filename, id, package_id)

    return fragments_dict


def ftpconnect(host=FTP_HOST):
    ftp = FTP()
    ftp.connect(host, FTP_PORT)
    ftp.login(FTP_USERNAME, FTP_PASSWORD)
    return ftp


def get_random_md5():
    random_bytes = os.urandom(16)
    md5 = hashlib.md5()
    md5.update(random_bytes)
    return md5.hexdigest()


def download_file(ftp, ftp_url, save_path):
    file_md5 = get_random_md5()
    bufsize = 1024
    write_path = os.path.join(save_path, '{}.zip'.format(file_md5))
    with open(write_path, 'wb') as file:
        print('存储位置:', write_path)
        print('下载路径:', ftp_url)
        ftp.retrbinary("RETR " + ftp_url, file.write, bufsize)
        ftp.set_debuglevel(0)
        ftp.close()
    return write_path


async def process_ftp_zip(ftp_url, package_id, user_id):
    ftp = ftpconnect()
    write_path = download_file(ftp, ftp_url, TMP_DIR)
    with open(write_path, 'rb') as file:
        await process_zip(file.read(), package_id, user_id)
