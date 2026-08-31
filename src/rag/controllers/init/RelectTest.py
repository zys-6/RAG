import json
import asyncio

# 示例类
class Risk:
    async def analyze(self, prompt):
        await asyncio.sleep(0.2)
        return f"[ModuleA] 处理：{prompt}"

class Delay:
    async def analyze(self, prompt):
        await asyncio.sleep(0.2)
        return f"[ModuleB] 分析：{prompt}"

# 主逻辑：通过 class 名和 method 名来调用
async def generate_report_from_json(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    tasks = []

    for module_cfg in config["modules"]:
        class_name = module_cfg["class"]
        method_name = module_cfg["method"]
        prompt = module_cfg["prompt"]

        # 获取类（从全局 namespace）
        cls = globals().get(class_name)
        if cls is None:
            raise ValueError(f"未找到类: {class_name}")

        # 实例化类
        instance = cls()

        # 获取方法
        method = getattr(instance, method_name, None)
        if method is None:
            raise ValueError(f"类 {class_name} 中未找到方法: {method_name}")

        # 加入异步任务
        tasks.append(method(prompt))

    # 执行所有异步任务
    results = await asyncio.gather(*tasks)

    # 生成 markdown
    markdown = "# 自动报告\n\n"
    for module, result in zip(config["modules"], results):
        markdown += f"## {module['name']}\n\n{result}\n\n"

    return markdown

# 示例运行
if __name__ == "__main__":
    report = asyncio.run(generate_report_from_json("moudle.json"))
    print(report)
