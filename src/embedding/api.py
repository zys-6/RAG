import math
import os
from typing import List, Union

import text2vec
import torch
from fastapi import FastAPI, Body, applications

from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html

from pydantic import BaseModel, Extra
from transformers import AutoTokenizer, AutoModelForSequenceClassification



def swagger_monkey_patch(*args, **kwargs):
    return get_swagger_ui_html(
        *args,
        **kwargs,
        swagger_js_url="static/swagger-ui-bundle-min.js",
        swagger_css_url="static/swagger-ui-min.css"
    )


applications.get_swagger_ui_html = swagger_monkey_patch

app = FastAPI()

app.mount("/static", StaticFiles(directory="embedding/static", html=True))
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"],
                   allow_headers=["*"])

embedding_model = text2vec.SentenceModel(os.environ.get("EMBEDDING_MODEL_PATH", "/models/text2vec-base-multilingual"))
reranker_tokenizer = AutoTokenizer.from_pretrained(os.environ.get("RERANKER_MODEL_PATH", '/models/reranker'))
reranker_model = AutoModelForSequenceClassification.from_pretrained(os.environ.get("RERANKER_MODEL_PATH",
                                                                                  '/models/reranker'))
rerank_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
reranker_model.to(rerank_device)
reranker_model.eval()


class EmbeddingInput(BaseModel):
    input: Union[str, List[str], List[List[int]]]

    class Config:
        extra = Extra.ignore


class EmbeddingItem(BaseModel):
    embedding: List[float]
    index: int
    object: str = "embedding"


class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingOutput(BaseModel):
    data: List[EmbeddingItem]
    model: str
    object: str = "list"
    usage: EmbeddingUsage


@app.post("/embeddings")
async def handler(input: EmbeddingInput):
    if isinstance(input.input, str):
        input.input = [input.input]
    data = []
    for index, _embedding in enumerate(embedding_model.encode(input.input, convert_to_numpy=False)):
        data.append(EmbeddingItem(embedding=_embedding.tolist(), index=index))
    num_tokens = sum(list(map(len, input.input)))
    output = EmbeddingOutput(data=data,
                             model="embeddings",
                             usage=EmbeddingUsage(prompt_tokens=num_tokens, total_tokens=num_tokens))
    return output


@app.post("/rerank")
async def handler(query: str = Body(...), texts: List[str] = Body(...)):
    batch_size = 32
    pairs = [[query, text] for text in texts]
    num = math.ceil(len(pairs) / batch_size)
    _scores = []
    _softmax_scores = []
    for idx in range(num):
        batch = pairs[idx * batch_size: (idx + 1) * batch_size]
        with torch.no_grad():
            inputs = reranker_tokenizer(batch, padding=True, truncation=True, return_tensors='pt', max_length=512)
            inputs = {key: value.to(rerank_device) for key, value in inputs.items()}
            scores = reranker_model(**inputs, return_dict=True).logits.view(-1, ).float().cpu()
            _scores.append(scores)
    _scores = torch.concat(_scores, dim=0)
    return {"scores": _scores.numpy().tolist(), "softmax_scores": _scores.softmax(-0).numpy().tolist()}
