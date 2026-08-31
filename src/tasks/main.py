import json
import os

from celery import Celery

from document_fragment.document.pdf_document import PdfDocument
from document_fragment.document.word_document import WordDocument
from utils.redis import client as redis_client
from utils.utils import get_hash_code


def process_word_core(content: bytes):
    word = WordDocument(filepath=content)
    return word.fragments


def process_pdf_core(content: bytes, max_threads: int):
    pdf = PdfDocument(filepath=content, max_threads=max_threads)
    return pdf.fragments


CELERY_BROKER = os.environ.get("CELERY_BROKER", None)

if CELERY_BROKER:
    app = Celery("document_fragment_tasks", broker=CELERY_BROKER)


    @app.task(bind=True)
    def process_word(self, content: bytes):
        fragments = process_word_core(content)
        """使用redis进行结果的保存"""
        fragments = [fragment.to_json() for fragment in fragments]
        redis_client.hset("document_fragment_result", get_hash_code(content), json.dumps(fragments))
