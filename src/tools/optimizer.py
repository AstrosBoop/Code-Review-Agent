"""
代码优化建议工具
"""
import re


def suggest_optimizations(code: str) -> dict:
    """
    分析代码并给出性能优化建议
    """
    results = {
        "suggestions": [],
        "score": 100
    }

    # 检测列表推导式优化机会
    for_append = re.findall(r'for\s+\w+\s+in\s+.+:\s*\n\s+\w+\.append\(', code)
    if for_append:
        results["suggestions"].append({
            "type": "performance",
            "message": f"发现 {len(for_append)} 处 for 循环 + append 模式，可改写为列表推导式，性能更好"
        })
        results["score"] -= 5

    # 检测重复的字典/列表访问
    repeated_access = re.findall(r'(\w+\[\w+\]).*\n.*\1', code)
    if repeated_access:
        results["suggestions"].append({
            "type": "performance",
            "message": "检测到重复的下标访问，建议缓存到临时变量中避免重复计算"
        })
        results["score"] -= 5

    # 检测字符串拼接
    str_concat = re.findall(r'\w+\s*\+=\s*["\']', code)
    if len(str_concat) > 2:
        results["suggestions"].append({
            "type": "performance",
            "message": f"发现 {len(str_concat)} 处字符串 += 拼接，大量字符串拼接建议使用 join() 或 f-string"
        })
        results["score"] -= 5

    # 检测 not in list（应用 set）
    not_in_list = re.findall(r'(not\s+in\s+\[|in\s+\[)', code)
    if len(not_in_list) > 1:
        results["suggestions"].append({
            "type": "performance",
            "message": "列表成员检测（in/not in list）时间复杂度为 O(n)，数据量大时建议改用 set，复杂度降为 O(1)"
        })
        results["score"] -= 5

    # 检测全局变量滥用
    global_vars = re.findall(r'^\s*global\s+\w+', code, re.MULTILINE)
    if len(global_vars) > 2:
        results["suggestions"].append({
            "type": "maintainability",
            "message": f"检测到 {len(global_vars)} 处 global 变量声明，过多全局变量影响代码可维护性，建议封装到类或函数参数中"
        })
        results["score"] -= 8

    # 检测异常处理过于宽泛
    bare_except = re.findall(r'except\s*:', code)
    except_exception = re.findall(r'except\s+Exception\s*:', code)
    if bare_except or except_exception:
        results["suggestions"].append({
            "type": "robustness",
            "message": "检测到过于宽泛的异常捕获（except: 或 except Exception:），建议捕获具体的异常类型"
        })
        results["score"] -= 8

    # 检测重复代码块（简单检测：相同行出现 3 次以上）
    lines = code.strip().split('\n')
    line_counts = {}
    for line in lines:
        stripped = line.strip()
        if len(stripped) > 20:
            line_counts[stripped] = line_counts.get(stripped, 0) + 1
    duplicates = {k: v for k, v in line_counts.items() if v >= 3}
    if duplicates:
        results["suggestions"].append({
            "type": "maintainability",
            "message": f"检测到 {len(duplicates)} 处重复代码，建议提取为公共函数"
        })
        results["score"] -= 10

    results["score"] = max(0, results["score"])
    return results
