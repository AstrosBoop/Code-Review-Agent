"""
代码质量分析工具
"""
import ast
import re


def analyze_code_quality(code: str) -> dict:
    """
    分析代码质量，包括复杂度、规范、可读性
    """
    results = {
        "issues": [],
        "metrics": {},
        "score": 100
    }

    lines = code.strip().split('\n')
    results["metrics"]["lines"] = len(lines)

    # 检测函数长度
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_lines = node.end_lineno - node.lineno + 1
                if func_lines > 50:
                    results["issues"].append({
                        "type": "complexity",
                        "severity": "medium",
                        "message": f"函数 '{node.name}' 过长（{func_lines} 行），建议拆分为更小的函数"
                    })
                    results["score"] -= 10

                # 检测参数数量
                args_count = len(node.args.args)
                if args_count > 5:
                    results["issues"].append({
                        "type": "complexity",
                        "severity": "low",
                        "message": f"函数 '{node.name}' 参数过多（{args_count} 个），建议使用对象封装"
                    })
                    results["score"] -= 5

        # 检测嵌套深度
        results["metrics"]["functions"] = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        results["metrics"]["classes"] = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        )

    except SyntaxError as e:
        results["issues"].append({
            "type": "syntax",
            "severity": "high",
            "message": f"语法错误: {str(e)}"
        })
        results["score"] -= 50

    # 检测命名规范
    bad_names = re.findall(r'\bdef\s+([A-Z][a-zA-Z]*)\s*\(', code)
    for name in bad_names:
        results["issues"].append({
            "type": "naming",
            "severity": "low",
            "message": f"函数名 '{name}' 应使用 snake_case 命名规范"
        })
        results["score"] -= 3

    # 检测魔法数字
    magic_numbers = re.findall(r'(?<!["\'\w])\b(?!0\b|1\b)\d+\b(?!["\'\w])', code)
    if len(magic_numbers) > 3:
        results["issues"].append({
            "type": "maintainability",
            "severity": "low",
            "message": f"代码中存在 {len(magic_numbers)} 个魔法数字，建议定义为常量"
        })
        results["score"] -= 5

    # 检测注释覆盖率
    comment_lines = sum(1 for line in lines if line.strip().startswith('#') or '"""' in line)
    comment_ratio = comment_lines / max(len(lines), 1)
    if comment_ratio < 0.1:
        results["issues"].append({
            "type": "documentation",
            "severity": "low",
            "message": "注释覆盖率不足 10%，建议增加必要的注释和文档字符串"
        })
        results["score"] -= 5

    results["score"] = max(0, results["score"])
    return results
