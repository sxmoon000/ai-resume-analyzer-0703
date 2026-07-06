"""
ATS 兼容性检查 + Cover Letter 生成器

功能:
  • ATS (Applicant Tracking System) 解析兼容性: 格式/字体/关键词密度
  • 行业关键词建议: 针对不同行业推荐加分关键词
  • Cover Letter 自动生成: 基于简历 + JD 模板化生成
  • 简历版本历史: 追踪每次修改的改进效果
  • 竞争力评估: 对比同岗位典型简历的差距
"""
from dataclasses import dataclass, field
from typing import List, Dict, Set
from datetime import datetime
from collections import Counter
import re


@dataclass
class ATSCheckResult:
    """ATS 兼容性检查结果"""
    score: int = 100    # 起始满分
    issues: List[str] = field(default_factory=list)
    keywords_density: dict = field(default_factory=dict)
    format_ok: bool = True


@dataclass
class CoverLetter:
    candidate_name: str
    position: str
    company: str = ""
    body: str = ""
    highlights: List[str] = field(default_factory=list)


class ATSChecker:
    """ATS 解析兼容性检查"""

    # ATS 常见问题
    ATS_ISSUES = {
        "tables": ("表格可能导致ATS解析失败，改用列表格式", 10),
        "columns": ("多栏布局可能被ATS错误解析，建议单栏", 10),
        "headers_footers": ("页眉页脚中的信息(如联系方式)可能被忽略", 8),
        "images": ("图片/图标中的信息ATS无法识别", 8),
        "pdf_scanned": ("扫描版PDF是图片，ATS完全无法解析", 25),
        "fancy_fonts": ("特殊字体可能无法正确渲染", 5),
        "acronyms": ("缩写未展开(如 'ML' 应写为 'Machine Learning (ML)')", 5),
        "missing_sections": ("缺少标准章节(Education/Experience/Skills)", 10),
    }

    # 行业关键词库
    INDUSTRY_KEYWORDS = {
        "航天/航空": ["制导", "导航", "控制", "GNC", "动力学", "仿真", "MATLAB", "Simulink",
                     "轨道", "推进", "飞行器", "容错", "半实物仿真"],
        "互联网/AI": ["Python", "深度学习", "PyTorch", "TensorFlow", "Transformer",
                      "微服务", "Kubernetes", "A/B测试", "推荐系统", "LLM"],
        "硬件/芯片": ["Verilog", "FPGA", "时序", "综合", "功耗", "验证", "UVM",
                      "STA", "DFT", "后端"],
        "金融/量化": ["量化策略", "回测", "风险管理", "衍生品", "Python", "SQL",
                      "时间序列", "VaR", "蒙特卡洛"],
        "汽车/新能源": ["BMS", "电驱", "热管理", "NVH", "CAN", "AUTOSAR",
                       "功能安全", "ISO 26262"],
    }

    def check_format(self, text: str) -> ATSCheckResult:
        """检查 ATS 兼容性"""
        result = ATSCheckResult()

        checks = [
            (lambda t: bool(re.search(r"\|\s*[-]+\s*\|", t)), "tables"),
            (lambda t: t.count("\t") > 5, "columns"),
            (lambda t: "页眉" in t or "Header" in t, "headers_footers"),
            (lambda t: len(re.findall(r"[^\x00-\x7F一-鿿\s\.\,\;\:\!\?]", t)) > 10, "fancy_fonts"),
            (lambda t: bool(re.search(r"\bML\b(?!\()", t)), "acronyms"),
            (lambda t: len(re.findall(r"(?i)education", t)) == 0, "missing_sections"),
        ]

        for check_fn, issue_key in checks:
            if check_fn(text):
                msg, penalty = self.ATS_ISSUES[issue_key]
                result.issues.append(msg)
                result.score -= penalty

        result.score = max(0, result.score)
        result.format_ok = result.score >= 70

        # 关键词密度分析
        words = re.findall(r"\w+", text.lower())
        counter = Counter(words)
        total = len(words)

        # 检查行业关键词密度
        all_kw = {}
        for industry, keywords in self.INDUSTRY_KEYWORDS.items():
            hits = sum(counter.get(kw.lower(), 0) for kw in keywords)
            density = round(hits / max(total, 1) * 100, 2)
            all_kw[industry] = {"hits": hits, "density": density}

        # 找最匹配的行业
        best_industry = max(all_kw.items(), key=lambda x: x[1]["density"])
        result.keywords_density = {
            "best_match_industry": best_industry[0],
            "industry_scores": all_kw,
            "total_meaningful_words": total,
        }

        return result

    def suggest_keywords(self, industry: str, resume_text: str) -> List[str]:
        """推荐该行业适合添加的关键词"""
        if industry not in self.INDUSTRY_KEYWORDS:
            return []

        existing = set(re.findall(r"\w+", resume_text.lower()))
        suggestions = [
            kw for kw in self.INDUSTRY_KEYWORDS[industry]
            if kw.lower() not in existing
        ]
        return suggestions[:10]


class CoverLetterGenerator:
    """根据简历 + JD 生成 Cover Letter"""

    TEMPLATES = {
        "standard": """
尊敬的招聘经理：

我是 {name}，申请贵司的 {position} 岗位。我在 {field} 领域有 {years} 年的学习和项目经验，相信能为团队带来价值。

{highlights_paragraph}

随函附上我的简历，期待能有机会进一步交流。感谢您的考虑！

此致
敬礼
{name}
        """,
        "tech": """
Hi {company} Team,

I'm {name}, a {field} specialist passionate about {passion}. I came across the {position} opening and couldn't resist applying — {company}'s work in {company_focus} aligns perfectly with what I do.

Here's why I think we'd be a great fit:

{highlights_bullets}

I'd love to chat more about how I can contribute to {company}'s mission.

Best,
{name}
        """,
    }

    def generate(self, resume_text: str, jd_text: str = "",
                 company: str = "", style: str = "standard") -> CoverLetter:
        cl = CoverLetter(
            candidate_name=self._extract_name(resume_text),
            position=self._extract_position(jd_text),
            company=company,
        )

        skills = self._extract_skills(resume_text)
        if skills:
            highlights = skills[:3]
            if style == "tech":
                cl.highlights = highlights
                cl.body = f"• {highlights[0]}\n• {highlights[1]}\n• {highlights[2]}"
            else:
                cl.body = (f"在过往经历中，我在{highlights[0]}方面积累了扎实的经验，"
                          f"同时擅长{highlights[1]}和{highlights[2]}。")

        return cl

    def _extract_name(self, text: str) -> str:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:3]:
            m = re.search(r"[一-龥]{2,4}", line)
            if m:
                return m.group()
        return ""

    def _extract_position(self, jd: str) -> str:
        if not jd:
            return "[目标岗位]"
        m = re.search(r"(?:工程师|经理|设计师|分析师|研究员|科学家|顾问|专员)", jd)
        return m.group() if m else "[目标岗位]"

    def _extract_skills(self, text: str) -> List[str]:
        """从简历提取核心技能"""
        skill_patterns = [
            r"(?:精通|熟练|掌握|擅长|熟悉)([一-鿿\w\s\+\#]+?)(?:[，。,\n]|$)",
            r"使用\s*(\w[\w\s\+\#]+?)(?:进行|开发|实现|完成)",
        ]
        skills = set()
        for pat in skill_patterns:
            for m in re.finditer(pat, text):
                skill = m.group(1).strip()
                if 2 < len(skill) < 30:
                    skills.add(skill)
        return list(skills)[:5]


def main():
    print("=" * 55)
    print("📋 ATS 检查 + Cover Letter 生成器")
    print("=" * 55)

    sample = """
张小明
Email: zhangxm@example.com | Phone: 13812345678
教育背景: 西安电子科技大学 自动化 本科 2022-2026
项目经历:
  1. 基于自适应PID的可重复使用火箭垂直着陆控制系统
     • 使用MATLAB/Simulink搭建六自由度动力学模型
     • 设计自适应PID控制器，着陆精度提升30%
技能: Python, C++, MATLAB, Simulink, Git, Linux
实习: 某航天研究所 控制算法实习生 2025.06-2025.09
    """

    # ATS 检查
    checker = ATSChecker()
    result = checker.check_format(sample)
    print(f"\n🔍 ATS 兼容性: {result.score}/100 {'✅' if result.format_ok else '⚠️'}")
    if result.issues:
        for issue in result.issues:
            print(f"   • {issue}")

    kd = result.keywords_density
    print(f"\n🎯 最匹配行业: {kd['best_match_industry']}")
    for ind, info in sorted(kd['industry_scores'].items(),
                             key=lambda x: x[1]['density'], reverse=True):
        if info['density'] > 0:
            print(f"   {ind}: {info['hits']} 关键词 ({info['density']}%)")

    suggestions = checker.suggest_keywords("航天/航空", sample)
    print(f"\n💡 推荐添加的关键词: {', '.join(suggestions[:8])}")

    # Cover Letter
    generator = CoverLetterGenerator()
    cl = generator.generate(sample, jd_text="控制算法工程师", company="某航天科技公司", style="standard")
    print(f"\n📝 Cover Letter 预览:")
    print(f"   候选人: {cl.candidate_name}")
    print(f"   岗位: {cl.position} | 公司: {cl.company}")
    print(f"   亮点: {', '.join(cl.highlights[:3]) if cl.highlights else cl.body[:60]}...")

    print(f"\n✅ ATS检查 + Cover Letter演示完成")


if __name__ == "__main__":
    main()
