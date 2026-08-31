"""抽取模型"""
import io
import math
import os
import xml.etree.ElementTree as ET
from collections import defaultdict

import cv2
import numpy as np
import requests
from PIL import Image
from fastapi import FastAPI, File, UploadFile, Path
from fitz import Rect

import document_fragment.document.layout.postprocess as postprocess

DET_MODEL_PATH = os.environ.get("DET_MODEL_PATH", None)
REG_MODEL_PATH = os.environ.get("REG_MODEL_PATH", None)
DET_MODEL_DEVICE = os.environ.get("DET_MODEL_DEVICE", "cpu")
REG_MODEL_DEVICE = os.environ.get("REG_MODEL_DEVICE", "cpu")

if DET_MODEL_PATH or REG_MODEL_PATH:
    from transformers import AutoModelForObjectDetection, TableTransformerForObjectDetection
    from torchvision import transforms
    import torch
    from paddleocr import PPStructure, PaddleOCR


class MaxResize:

    def __init__(self, max_size: int = 800):
        self.max_size = max_size

    def __call__(self, image):
        width, height = image.size
        curr_max_size = max(width, self.max_size)
        scale = self.max_size / curr_max_size
        width, height = math.ceil(scale * width), math.ceil(scale * height)
        resized_image = image.resize((width, height))
        return resized_image


# class StructureLabel(enum.Enum):
#     text
#     title
#     figure
#     figure_caption
#     table
#     table_caption
#     header
#     footer
#     reference
#     equation


class TableExtractionPipeline:
    def __init__(self,
                 det_model_path: str = None,
                 reg_model_path: str = None,
                 det_model_device: str = "cpu",
                 reg_model_device: str = "cpu"):
        self.det_model_device = det_model_device
        self.reg_model_device = reg_model_device
        self.det_model_path = det_model_path
        self.reg_model_path = reg_model_path

        self.table_detection_model = AutoModelForObjectDetection.from_pretrained(
            det_model_path, revision="no_timm", local_files_only=True
        )
        self.table_detection_model.to(det_model_device)
        self.table_detection_model.eval()
        self.det_label2id = self.table_detection_model.config.label2id
        self.det_id2label = {v: k for k, v in self.det_label2id.items()}
        self.det_class_thresholds = {
            "table": 0.5,
            "table rotated": 0.5,
            "no object": 10
        }

        self.table_recognition_model = TableTransformerForObjectDetection.from_pretrained(
            reg_model_path, local_files_only=True
        )
        self.table_recognition_model.to(reg_model_device)
        self.table_recognition_model.eval()
        self.reg_label2id = self.table_recognition_model.config.label2id
        self.reg_id2label = {v: k for k, v in self.reg_label2id.items()}
        self.reg_class_thresholds = {
            "table": 0.5,
            "table column": 0.5,
            "table row": 0.5,
            "table column header": 0.5,
            "table projected row header": 0.5,
            "table spanning cell": 0.5,
            "no object": 10
        }

        self.det_transform = transforms.Compose([
            MaxResize(800),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

        self.reg_transform = transforms.Compose([
            MaxResize(1000),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

    @classmethod
    def rescale_bbox(cls, bbox, width, height):
        def _cxcywh_to_xyxy(x):
            x_c, y_c, w, h = x.unbind(-1)
            b = [(x_c - 0.5 * w), (y_c - 0.5 * h), (x_c + 0.5 * w), (y_c + 0.5 * h)]
            return torch.stack(b, dim=1)

        bbox = _cxcywh_to_xyxy(bbox)
        bbox = bbox * torch.tensor([width, height, width, height], dtype=torch.float32)
        return bbox

    @classmethod
    def convert_outputs_to_objects(cls, outputs, width, height, id2label):
        result = outputs.logits.softmax(-1).max(-1)
        pred_labels = list(result.indices.detach().cpu().numpy())[0]
        pred_scores = list(result.values.detach().cpu().numpy())[0]
        pred_bboxes = [item.tolist() for item in cls.rescale_bbox(outputs['pred_boxes'].detach().cpu()[0],
                                                                  width, height)]
        ret = []
        for label, score, bbox in zip(pred_labels, pred_scores, pred_bboxes):
            if int(label) in id2label:
                ret.append({
                    "label": id2label[int(label)], "score": float(score),
                    "bbox": [float(item) for item in bbox]
                })
        return ret

    @classmethod
    def refine_table_structure(cls, table_structure, class_thresholds):
        """
        Apply operations to the detected table structure objects such as
        thresholding, NMS, and alignment.
        """
        rows = table_structure["rows"]
        columns = table_structure['columns']

        # Process the headers
        column_headers = table_structure['column headers']
        column_headers = postprocess.apply_threshold(column_headers, class_thresholds["table column header"])
        column_headers = postprocess.nms(column_headers)
        column_headers = postprocess.align_headers(column_headers, rows)

        # Process spanning cells
        spanning_cells = [elem for elem in table_structure['spanning cells'] if not elem['projected row header']]
        projected_row_headers = [elem for elem in table_structure['spanning cells'] if elem['projected row header']]
        spanning_cells = postprocess.apply_threshold(spanning_cells, class_thresholds["table spanning cell"])
        projected_row_headers = postprocess.apply_threshold(projected_row_headers,
                                                            class_thresholds["table projected row header"])
        spanning_cells += projected_row_headers
        # Align before NMS for spanning cells because alignment brings them into agreement
        # with rows and columns first; if spanning cells still overlap after this operation,
        # the threshold for NMS can basically be lowered to just above 0
        spanning_cells = postprocess.align_supercells(spanning_cells, rows, columns)
        spanning_cells = postprocess.nms_supercells(spanning_cells)

        postprocess.header_supercell_tree(spanning_cells)

        table_structure['columns'] = columns
        table_structure['rows'] = rows
        table_structure['spanning cells'] = spanning_cells
        table_structure['column headers'] = column_headers

        return table_structure

    @classmethod
    def convert_objects_to_structures(cls, objects, tokens, class_thresholds):
        tables = [obj for obj in objects if obj['label'] == 'table']
        table_structures = []

        for table in tables:
            table_objects = [obj for obj in objects if postprocess.iob(obj['bbox'], table['bbox']) >= 0.5]
            table_tokens = [token for token in tokens if postprocess.iob(token['bbox'], table['bbox']) >= 0.5]

            structure = {}

            columns = [obj for obj in table_objects if obj['label'] == 'table column']
            rows = [obj for obj in table_objects if obj['label'] == 'table row']
            column_headers = [obj for obj in table_objects if obj['label'] == 'table column header']
            spanning_cells = [obj for obj in table_objects if obj['label'] == 'table spanning cell']
            for obj in spanning_cells:
                obj['projected row header'] = False
            projected_row_headers = [obj for obj in table_objects if obj['label'] == 'table projected row header']
            for obj in projected_row_headers:
                obj['projected row header'] = True
            spanning_cells += projected_row_headers
            for obj in rows:
                obj['column header'] = False
                for header_obj in column_headers:
                    if postprocess.iob(obj['bbox'], header_obj['bbox']) >= 0.5:
                        obj['column header'] = True

            # Refine table structures
            rows = postprocess.refine_rows(rows, table_tokens, class_thresholds['table row'])
            columns = postprocess.refine_columns(columns, table_tokens, class_thresholds['table column'])

            # Shrink table bbox to just the total height of the rows
            # and the total width of the columns
            row_rect = Rect()
            for obj in rows:
                row_rect.include_rect(obj['bbox'])
            column_rect = Rect()
            for obj in columns:
                column_rect.include_rect(obj['bbox'])
            table['row_column_bbox'] = [column_rect[0], row_rect[1], column_rect[2], row_rect[3]]
            table['bbox'] = table['row_column_bbox']

            # Process the rows and columns into a complete segmented table
            columns = postprocess.align_columns(columns, table['row_column_bbox'])
            rows = postprocess.align_rows(rows, table['row_column_bbox'])

            structure['rows'] = rows
            structure['columns'] = columns
            structure['column headers'] = column_headers
            structure['spanning cells'] = spanning_cells

            if len(rows) > 0 and len(columns) > 1:
                structure = cls.refine_table_structure(structure, class_thresholds)

            table_structures.append(structure)

        return table_structures

    @classmethod
    def convert_structures_to_cell(cls, table_structure, tokens):
        """
            Assuming the row, column, spanning cell, and header bounding boxes have
            been refined into a set of consistent table structures, process these
            table structures into table cells. This is a universal representation
            format for the table, which can later be exported to Pandas or CSV formats.
            Classify the cells as header/access cells or data cells
            based on if they intersect with the header bounding box.
            """
        columns = table_structure['columns']
        rows = table_structure['rows']
        spanning_cells = table_structure['spanning cells']
        cells = []
        subcells = []

        # Identify complete cells and subcells
        for column_num, column in enumerate(columns):
            for row_num, row in enumerate(rows):
                column_rect = Rect(list(column['bbox']))
                row_rect = Rect(list(row['bbox']))
                cell_rect = row_rect.intersect(column_rect)
                header = 'column header' in row and row['column header']
                cell = {'bbox': list(cell_rect), 'column_nums': [column_num], 'row_nums': [row_num],
                        'column header': header}

                cell['subcell'] = False
                for spanning_cell in spanning_cells:
                    spanning_cell_rect = Rect(list(spanning_cell['bbox']))
                    if (spanning_cell_rect.intersect(cell_rect).get_area()
                        / cell_rect.get_area()) > 0.5:
                        cell['subcell'] = True
                        break

                if cell['subcell']:
                    subcells.append(cell)
                else:
                    # cell text = extract_text_inside_bbox(table_spans, cell['bbox'])
                    # cell['cell text'] = cell text
                    cell['projected row header'] = False
                    cells.append(cell)

        for spanning_cell in spanning_cells:
            spanning_cell_rect = Rect(list(spanning_cell['bbox']))
            cell_columns = set()
            cell_rows = set()
            cell_rect = None
            header = True
            for subcell in subcells:
                subcell_rect = Rect(list(subcell['bbox']))
                subcell_rect_area = subcell_rect.get_area()
                if (subcell_rect.intersect(spanning_cell_rect).get_area()
                    / subcell_rect_area) > 0.5:
                    if cell_rect is None:
                        cell_rect = Rect(list(subcell['bbox']))
                    else:
                        cell_rect.include_rect(Rect(list(subcell['bbox'])))
                    cell_rows = cell_rows.union(set(subcell['row_nums']))
                    cell_columns = cell_columns.union(set(subcell['column_nums']))
                    # By convention here, all subcells must be classified
                    # as header cells for a spanning cell to be classified as a header cell;
                    # otherwise, this could lead to a non-rectangular header region
                    header = header and 'column header' in subcell and subcell['column header']
            if len(cell_rows) > 0 and len(cell_columns) > 0:
                cell = {'bbox': list(cell_rect), 'column_nums': list(cell_columns), 'row_nums': list(cell_rows),
                        'column header': header, 'projected row header': spanning_cell['projected row header']}
                cells.append(cell)

        # Compute a confidence score based on how well the page tokens
        # slot into the cells reported by the model
        _, _, cell_match_scores = postprocess.slot_into_containers(cells, tokens)
        try:
            mean_match_score = sum(cell_match_scores) / len(cell_match_scores)
            min_match_score = min(cell_match_scores)
            confidence_score = (mean_match_score + min_match_score) / 2
        except:
            confidence_score = 0

        # Dilate rows and columns before final extraction
        # dilated_columns = fill_column_gaps(columns, table_bbox)
        dilated_columns = columns
        # dilated_rows = fill_row_gaps(rows, table_bbox)
        dilated_rows = rows
        for cell in cells:
            column_rect = Rect()
            for column_num in cell['column_nums']:
                column_rect.include_rect(list(dilated_columns[column_num]['bbox']))
            row_rect = Rect()
            for row_num in cell['row_nums']:
                row_rect.include_rect(list(dilated_rows[row_num]['bbox']))
            cell_rect = column_rect.intersect(row_rect)
            cell['bbox'] = list(cell_rect)

        span_nums_by_cell, _, _ = postprocess.slot_into_containers(cells, tokens, overlap_threshold=0.001,
                                                                   unique_assignment=True, forced_assignment=False)

        for cell, cell_span_nums in zip(cells, span_nums_by_cell):
            cell_spans = [tokens[num] for num in cell_span_nums]
            # TODO: Refine how text is extracted; should be character-based, not span-based;
            # but need to associate
            cell['cell text'] = postprocess.extract_text_from_spans(cell_spans, remove_integer_superscripts=False)
            cell['spans'] = cell_spans

        # Adjust the row, column, and cell bounding boxes to reflect the extracted text
        num_rows = len(rows)
        rows = postprocess.sort_objects_top_to_bottom(rows)
        num_columns = len(columns)
        columns = postprocess.sort_objects_left_to_right(columns)
        min_y_values_by_row = defaultdict(list)
        max_y_values_by_row = defaultdict(list)
        min_x_values_by_column = defaultdict(list)
        max_x_values_by_column = defaultdict(list)
        for cell in cells:
            min_row = min(cell["row_nums"])
            max_row = max(cell["row_nums"])
            min_column = min(cell["column_nums"])
            max_column = max(cell["column_nums"])
            for span in cell['spans']:
                min_x_values_by_column[min_column].append(span['bbox'][0])
                min_y_values_by_row[min_row].append(span['bbox'][1])
                max_x_values_by_column[max_column].append(span['bbox'][2])
                max_y_values_by_row[max_row].append(span['bbox'][3])
        for row_num, row in enumerate(rows):
            if len(min_x_values_by_column[0]) > 0:
                row['bbox'][0] = min(min_x_values_by_column[0])
            if len(min_y_values_by_row[row_num]) > 0:
                row['bbox'][1] = min(min_y_values_by_row[row_num])
            if len(max_x_values_by_column[num_columns - 1]) > 0:
                row['bbox'][2] = max(max_x_values_by_column[num_columns - 1])
            if len(max_y_values_by_row[row_num]) > 0:
                row['bbox'][3] = max(max_y_values_by_row[row_num])
        for column_num, column in enumerate(columns):
            if len(min_x_values_by_column[column_num]) > 0:
                column['bbox'][0] = min(min_x_values_by_column[column_num])
            if len(min_y_values_by_row[0]) > 0:
                column['bbox'][1] = min(min_y_values_by_row[0])
            if len(max_x_values_by_column[column_num]) > 0:
                column['bbox'][2] = max(max_x_values_by_column[column_num])
            if len(max_y_values_by_row[num_rows - 1]) > 0:
                column['bbox'][3] = max(max_y_values_by_row[num_rows - 1])
        for cell in cells:
            row_rect = Rect()
            column_rect = Rect()
            for row_num in cell['row_nums']:
                row_rect.include_rect(list(rows[row_num]['bbox']))
            for column_num in cell['column_nums']:
                column_rect.include_rect(list(columns[column_num]['bbox']))
            cell_rect = row_rect.intersect(column_rect)
            if cell_rect.get_area() > 0:
                cell['bbox'] = list(cell_rect)
                pass

        return cells, confidence_score

    @classmethod
    def convert_cells_to_html(cls, cells):
        cells = sorted(cells, key=lambda k: min(k['column_nums']))
        cells = sorted(cells, key=lambda k: min(k['row_nums']))

        table = ET.Element("table")
        current_row = -1

        for cell in cells:
            this_row = min(cell['row_nums'])

            attrib = {}
            colspan = len(cell['column_nums'])
            if colspan > 1:
                attrib['colspan'] = str(colspan)
            rowspan = len(cell['row_nums'])
            if rowspan > 1:
                attrib['rowspan'] = str(rowspan)
            if this_row > current_row:
                current_row = this_row
                if cell['column header']:
                    cell_tag = "th"
                    row = ET.SubElement(table, "thead")
                else:
                    cell_tag = "td"
                    row = ET.SubElement(table, "tr")
            tcell = ET.SubElement(row, cell_tag, attrib=attrib)
            tcell.text = cell['cell text']

        return str(ET.tostring(table, encoding="unicode", short_empty_elements=False))

    def detect(self, image):
        img_tensor = self.det_transform(image).unsqueeze(0).to(self.det_model_device)
        outputs = self.table_detection_model(img_tensor)
        result = outputs.logits.softmax(-1).max(-1)
        pred_labels = list(result.indices.detach().cpu().numpy())[0]
        pred_scores = list(result.values.detach().cpu().numpy())[0]
        pred_bboxes = [item.tolist() for item in self.rescale_bbox(outputs['pred_boxes'].detach().cpu()[0],
                                                                   image.width, image.height)]
        ret = []
        for label, score, bbox in zip(pred_labels, pred_scores, pred_bboxes):
            if int(label) in self.det_id2label:
                ret.append({
                    "label": self.det_id2label[int(label)], "score": float(score),
                    "bbox": [float(item) for item in bbox]
                })
        return ret

    def recognize(self, image, tokens):

        img_tensor = self.reg_transform(image).unsqueeze(0).to(self.reg_model_device)

        outputs = self.table_recognition_model(img_tensor)

        objects = self.convert_outputs_to_objects(outputs, image.width, image.height, self.reg_id2label)

        structures = self.convert_objects_to_structures(objects, tokens, self.reg_class_thresholds)

        cells = [self.convert_structures_to_cell(structure, tokens)[0] for structure in structures]

        htmls = [self.convert_cells_to_html(cells) for cells in cells]
        return htmls


if DET_MODEL_PATH and REG_MODEL_PATH:
    table_extraction_pipeline = TableExtractionPipeline(det_model_path=DET_MODEL_PATH,
                                                        det_model_device=DET_MODEL_DEVICE,
                                                        reg_model_path=REG_MODEL_PATH,
                                                        reg_model_device=REG_MODEL_DEVICE
                                                        )
    ch_structure_engine = PPStructure(table=False, ocr=False, show_log=False, lang="ch", layout_score_threshold=0.5,
                                      use_gpu=False, use_multiprocess=False)
    en_structure_engine = PPStructure(table=False, ocr=False, show_log=False, lang="en", layout_score_threshold=0.5,
                                      use_gpu=False, use_multiprocess=False)
    ch_ocr_engine = PaddleOCR(use_angle_cls=False, lang="ch", )
    en_ocr_engine = PaddleOCR(use_angle_cls=False, lang="en")
else:
    table_extraction_pipeline = None
    ch_structure_engine = None
    en_structure_engine = None
    ch_ocr_engine = None
    en_ocr_engine = None


def get_table_extraction_pipeline():
    if table_extraction_pipeline:
        return table_extraction_pipeline
    else:
        """调用本地api"""

        class TableExtractPipelineProxy:
            @staticmethod
            def detect(img: Image):
                bytes_io = io.BytesIO()
                img.save(bytes_io, format="PNG")
                resp = requests.post("http://model:5006/table", files={"image": bytes_io.getvalue()})
                return resp.json()

        return TableExtractPipelineProxy()


def get_structure_engine(lang: str = "zh"):
    if lang == "zh":
        ret = ch_structure_engine
    else:
        ret = en_structure_engine
    if ret:
        return ret
    else:
        class StructureEngineProxy:
            def __call__(self, img_cv2):
                img = cv2.imencode(".png", img_cv2)[1].tostring()
                resp = requests.post(f"http://model:5006/structure/{lang}", files={"image": img})
                return resp.json()

        return StructureEngineProxy()


def get_ocr_engine(lang: str = "zh"):
    if lang == "zh":
        ret = ch_ocr_engine
    else:
        ret = en_ocr_engine
    if ret:
        return ret
    else:
        class OCREngineProxy:
            @staticmethod
            def ocr(img, cls=False):
                resp = requests.post(f"http://model:5006/ocr/{lang}", files={"image": img})
                return resp.json()

        return OCREngineProxy()


def create_app():
    app = FastAPI()

    @app.post("/table")
    async def handler(image: UploadFile = File(...)):
        content = await image.read()
        img = Image.open(io.BytesIO(content))
        table_engine = get_table_extraction_pipeline()
        return table_engine.detect(img)

    @app.post("/structure/{lang}")
    async def handler(lang: str = Path(...), image: UploadFile = File(...)):
        content = await image.read()
        img = Image.open(io.BytesIO(content))
        structure_engine = get_structure_engine(lang)
        img_cv2 = cv2.cvtColor(np.array(img), cv2.COLOR_BGR2RGB)
        result = structure_engine(img_cv2)
        new_result = []
        for idx in range(len(result)):
            if result[idx]['type'] == 'figure':
                result[idx]['img'] = result[idx]['img'].tolist()
            elif result[idx]['type'] == 'table':
                continue
            else:
                del result[idx]['img']
            new_result.append(result[idx])
        return result

    @app.post("/ocr/{lang}")
    async def handler(lang: str = Path(...), image: UploadFile = File(...)):
        content = await image.read()
        img = Image.open(io.BytesIO(content))
        img_cv2 = cv2.cvtColor(np.array(img), cv2.COLOR_BGR2RGB)
        ocr_engine = get_ocr_engine(lang)
        return ocr_engine.ocr(img_cv2)

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run('document_fragment.document.layout.model:create_app',
                factory=True,
                host="0.0.0.0", port=5006, workers=4)
