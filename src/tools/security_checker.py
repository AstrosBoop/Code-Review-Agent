"""
安全漏洞检测工具
"""
import re


# 常见安全漏洞规则
SECURITY_RULES = [
    {
        "id": "SQL_INJECTION",
        "pattern": r'(execute|query|cursor\.execute)\s*\(\s*[f\'"].*(%s|\{|\+)',
        "severity": "high",
        "message": "潜在 SQL 注入风险：检测到字符串拼接构造 SQL 语句，建议使用参数化查询"
    },
    {
        "id": "HARDCODED_PASSWORD",
        "pattern": r'(password|passwd|pwd|secret|token|api_key)\s*=\s*["\'][^"\']{4,}["\']',
        "severity": "high",
        "message": "硬编码凭证：检测到密码/密钥直接写在代码中，建议使用环境变量"
    },
    {
        "id": "COMMAND_INJECTION",
        "pattern": r'(os\.system|subprocess\.call|subprocess\.run|eval|exec)\s*\(',
        "severity": "high",
        "message": "潜在命令注入风险：使用了危险函数，建议严格验证输入或使用更安全的替代方案"
    },
    {
        "id": "XSS",
        "pattern": r'innerHTML\s*=|document\.write\s*\(',
        "severity": "medium",
        "message": "潜在 XSS 风险：检测到直接操作 innerHTML，建议使用 textContent 或对输入进行转义"
    },
    {
        "id": "WEAK_CRYPTO",
        "pattern": r'(md5|sha1)\s*\(',
        "severity": "medium",
        "message": "弱加密算法：MD5/SHA1 已不安全，建议使用 SHA-256 或更强的算法"
    },
    {
        "id": "DEBUG_CODE",
        "pattern": r'(print\s*\(.*password|print\s*\(.*token|print\s*\(.*secret)',
        "severity": "medium",
        "message": "调试代码泄露敏感信息：检测到打印敏感数据，上线前需移除"
    },
    {
        "id": "INSECURE_RANDOM",
        "pattern": r'random\.(random|randint|choice)\s*\(',
        "severity": "low",
        "message": "不安全的随机数：用于安全场景时应使用 secrets 模块而非 random 模块"
    },
    {
        "id": "PATH_TRAVERSAL",
        "pattern": r'open\s*\(\s*[^)]*\+[^)]*\)',
        "severity": "medium",
        "message": "潜在路径遍历风险：文件路径通过拼接构造，建议使用 pathlib 并验证路径合法性"
    },
]


def check_security(code: str) -> dict:
    """
    检测代码中的安全漏洞
    """
    results = {
        "vulnerabilities": [],
        "risk_level": "low",
        "score": 100
    }

    for rule in SECURITY_RULES:
        matches = re.findall(rule["pattern"], code, re.IGNORECASE)
        if matches:
            results["vulnerabilities"].append({
                "id": rule["id"],
                "severity": rule["severity"],
                "message": rule["message"],
                "occurrences": len(matches)
            })
            if rule["severity"] == "high":
                results["score"] -= 30
            elif rule["severity"] == "medium":
                results["score"] -= 15
            else:
                results["score"] -= 5

    results["score"] = max(0, results["score"])

    high_count = sum(1 for v in results["vulnerabilities"] if v["severity"] == "high")
    medium_count = sum(1 for v in results["vulnerabilities"] if v["severity"] == "medium")

    if high_count > 0:
        results["risk_level"] = "high"
    elif medium_count > 0:
        results["risk_level"] = "medium"
    else:
        results["risk_level"] = "low"

    return results
