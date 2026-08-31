# import json
# import asyncio
# import os
# import pathlib
# from docx import Document
# from docx.oxml import ns
#
# from
#
# # ===== 示例类 =====
# class Risk:
#     async def analyze(self, prompt):
#         await asyncio.sleep(0.2)
#         return f"[Risk] 分析结果：{prompt}"
#
# class Delay:
#     async def analyze(self, prompt):
#         await asyncio.sleep(0.2)
#         return f"[Delay] 分析结果：{prompt}"
#
#
# # ===== 工具函数 =====
# def _add_heading(document, text, level):
#     document.add_heading(text, level=level)
#
# def _add_text(document, text):
#     document.add_paragraph(text)
#
#
# # ===== 模块运行（反射方式） =====
# async def run_modules_from_json(json_path):
#     with open(json_path, 'r', encoding='utf-8') as f:
#         config = json.load(f)
#
#     tasks = []
#     module_names = []
#
#     for module_cfg in config["modules"]:
#         cls = globals().get(module_cfg["class"])
#         if not cls:
#             raise ValueError(f"未找到类: {module_cfg['class']}")
#
#         instance = cls()
#         method = getattr(instance, module_cfg["method"], None)
#         if not method:
#             raise ValueError(f"类 {module_cfg['class']} 中未找到方法: {module_cfg['method']}")
#
#         tasks.append(method(module_cfg["prompt"]))
#         module_names.append(module_cfg["name"])
#
#     results = await asyncio.gather(*tasks)
#     return list(zip(module_names, results))
#
#
# # ===== 报告生成 =====
# async def generate_word_report(json_path, output_name="报告"):
#     module_results = await run_modules_from_json(json_path)
#
#     document = Document()
#     document.styles['Normal'].font.name = 'Times New Roman'
#     document.styles['Normal']._element.rPr.rFonts.set(ns.qn('w:eastAsia'), u'宋体')
#
#     _add_heading(document, output_name, 0)
#
#     for module_name, result in module_results:
#         _add_heading(document, module_name, 1)
#         _add_text(document, result)
#
#     doc_static_path = pathlib.Path(__file__).parent / 'static' / 'docx'
#     doc_static_path.mkdir(parents=True, exist_ok=True)
#     file_path = doc_static_path / f"{output_name}.docx"
#     document.save(file_path)
#
#     return {'generate_docx': str(file_path)}
#
#
# # ===== 运行入口 =====
# if __name__ == "__main__":
#     report_info = asyncio.run(generate_word_report("modules.json", output_name="项目分析报告"))
#     print(report_info)
