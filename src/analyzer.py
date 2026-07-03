"""
AI 简历分析器 — 结构检查 + 关键词提取 + 评分建议

功能: 解析简历文本/PDF → 检查结构完整性 → 提取技能关键词 →
     匹配 JD 需求 → 给出评分和改进建议。

刚需场景: 求职前检查简历是否有硬伤，对比JD看匹配度。

知识点:
  1. PDF 文本提取 (PyPDF2)
  2. 正则表达式匹配: 邮箱/电话/日期/学历
  3. 关键词提取: TF-IDF 风格词频
  4. JD 匹配度: 交集/并集覆盖率
  5. 结构化评分: 加权评分体系
"""
import re
import json
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Set

# ── 评分维度 ──
SCORE_WEIGHTS = {
    "structure": 0.25,    # 结构完整性
    "skills": 0.30,       # 技能关键词丰富度
    "experience": 0.25,   # 经验描述质量
    "jd_match": 0.20,     # JD匹配度 (需要JD输入)
}


@dataclass
class ResumeAnalysis:
    name: str = ""
    email: str = ""
    phone: str = ""
    sections: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    missing_sections: List[str] = field(default_factory=list)
    scores: dict = field(default_factory=dict)
    total_score: float = 0.0
    suggestions: List[str] = field(default_factory=list)
    jd_match_pct: float = 0.0
    jd_missing: List[str] = field(default_factory=list)


class ResumeAnalyzer:
    """简历分析引擎"""

    REQUIRED_SECTIONS = [
        "个人信息", "教育背景", "项目经历", "技能", "实习/工作经历"
    ]
    SECTION_KEYWORDS = {
        "个人信息": ["个人", "基本", "信息", "姓名", "联系"],
        "教育背景": ["教育", "学历", "学校", "大学", "学院"],
        "项目经历": ["项目", "经验", "经历", "project"],
        "技能": ["技能", "skill", "技术栈", "能力"],
        "实习/工作经历": ["实习", "工作", "经历", "experience", "intern"],
    }
    SKILL_DB = [
        "Python", "Java", "C++", "JavaScript", "TypeScript", "Go", "Rust",
        "SQL", "Docker", "Kubernetes", "AWS", "Linux", "Git",
        "机器学习", "深度学习", "NLP", "计算机视觉", "PyTorch", "TensorFlow",
        "React", "Vue", "Node.js", "Django", "Flask",
        "数据分析", "Pandas", "NumPy", "MATLAB", "Simulink",
        "项目管理", "敏捷", "Scrum", "团队协作", "沟通",
    ]

    def analyze(self, text: str, jd_text: str = "") -> ResumeAnalysis:
        r = ResumeAnalysis()
        text_lower = text.lower()

        # 1. 提取基本信息
        r.name = self._extract_name(text)
        r.email = self._find(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        r.phone = self._find(r"1[3-9]\d{9}", text)

        # 2. 章节检测
        for section, keywords in self.SECTION_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                r.sections.append(section)
        r.missing_sections = [s for s in self.REQUIRED_SECTIONS if s not in r.sections]

        # 3. 技能提取
        r.skills = sorted(set(s for s in self.SKILL_DB if s.lower() in text_lower))

        # 4. 评分
        # 结构分: 必需章节的完成度
        struct_score = (len(r.sections) / len(self.REQUIRED_SECTIONS)) * 100

        # 技能分: 技能关键词数量
        skill_score = min(100, len(r.skills) / 10 * 100)

        # 经验分: 数字量化描述 (如 "提高了30%")
        numbers = len(re.findall(r"\d+[%％倍]", text))
        bullets = len(re.findall(r"[•\-●✓√]", text))
        exp_score = min(100, (numbers * 15 + bullets * 5))

        r.scores = {
            "structure": round(struct_score),
            "skills": round(skill_score),
            "experience": round(exp_score),
        }

        # 5. JD 匹配度
        if jd_text:
            jd_words = set(re.findall(r"\w+", jd_text.lower()))
            resume_words = set(re.findall(r"\w+", text_lower))
            jd_skills = {s for s in self.SKILL_DB if s.lower() in jd_text.lower()}
            resume_skills = {s.lower() for s in r.skills}
            if jd_skills:
                r.jd_match_pct = round(len(resume_skills & jd_skills) / len(jd_skills) * 100)
                r.jd_missing = sorted(jd_skills - resume_skills)
            r.scores["jd_match"] = r.jd_match_pct

        # 综合分
        r.total_score = round(sum(
            r.scores.get(k, 0) * w for k, w in SCORE_WEIGHTS.items()
        ))

        # 6. 建议
        r.suggestions = self._gen_suggestions(r)

        return r

    def _extract_name(self, text: str) -> str:
        """提取姓名 (简历开头第一行多为姓名)"""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:3]:
            # 中文姓名: 2-4个汉字
            m = re.search(r"[一-龥]{2,4}", line)
            if m:
                return m.group()
        return "未知"

    def _find(self, pattern: str, text: str) -> str:
        m = re.search(pattern, text)
        return m.group() if m else ""

    def _gen_suggestions(self, r: ResumeAnalysis) -> List[str]:
        tips = []
        if r.missing_sections:
            tips.append(f"❌ 缺少章节: {', '.join(r.missing_sections)}")
        if not r.email:
            tips.append("❌ 未找到邮箱地址")
        if not r.phone:
            tips.append("❌ 未找到手机号")
        if r.scores["structure"] < 60:
            tips.append("📝 简历结构不完整，建议补充缺失章节")
        if r.scores["skills"] < 50:
            tips.append("💡 技能关键词偏少，建议补充技术栈")
        if r.scores["experience"] < 40:
            tips.append("📊 经验描述建议用数字量化成果 (如 '提升30%')")
        if r.jd_missing:
            tips.append(f"🎯 JD 中提及但简历缺少的技能: {', '.join(r.jd_missing[:5])}")
        if not tips:
            tips.append("✅ 简历整体质量不错！")
        return tips

    def report(self, r: ResumeAnalysis):
        print("=" * 55)
        print("📝 AI 简历分析报告")
        print("=" * 55)
        print(f"\n👤 姓名: {r.name}")
        print(f"📧 邮箱: {r.email or '未检测到'}")
        print(f"📱 电话: {r.phone or '未检测到'}")
        print(f"\n📂 检测到章节: {', '.join(r.sections) if r.sections else '未检测到'}")
        print(f"⚠️  缺失章节: {', '.join(r.missing_sections) if r.missing_sections else '无 — 完整!'}")

        print(f"\n🔧 技能关键词 ({len(r.skills)}个):")
        print(f"   {', '.join(r.skills[:15])}{'...' if len(r.skills) > 15 else ''}")

        print(f"\n📊 评分:")
        for dim, score in r.scores.items():
            bar = "█" * (score // 5) + "░" * (20 - score // 5)
            print(f"   {dim:<12} {bar} {score}/100")
        print(f"   {'─' * 36}")
        print(f"   {'综合':<12} {'█' * (r.total_score // 5) + '░' * (20 - r.total_score // 5)} {r.total_score}/100")

        if r.jd_match_pct:
            print(f"\n🎯 JD 匹配度: {r.jd_match_pct}%")

        print(f"\n💡 建议:")
        for tip in r.suggestions:
            print(f"   {tip}")


# ── Demo ──
def main():
    sample_resume = """
张小明
Email: zhangxm@example.com | Phone: 13812345678

教育背景
西安电子科技大学 | 自动化专业 | 本科 | 2022-2026
GPA: 3.8/4.0

项目经历
基于自适应PID的可重复使用火箭垂直着陆控制系统
• 使用MATLAB/Simulink搭建火箭着陆六自由度动力学模型
• 设计自适应PID控制器，着陆精度提升30%相比传统PID
• 编写 Python 脚本自动生成仿真报告，效率提升 50%
• 技术栈: MATLAB, Simulink, Python, 控制理论

技能
编程语言: Python, C++, MATLAB
工具: Simulink, Git, Docker, Linux
理论: 自动控制原理, 自适应控制, 最优控制

实习经历
某航天研究所 | 控制算法实习生 | 2025.06-2025.09
• 参与火箭着陆段制导算法仿真验证
• 使用 Python 和 MATLAB 进行数据处理与可视化
"""

    sample_jd = """
控制算法工程师
要求:
1. 熟悉经典控制理论与现代控制理论
2. 精通 MATLAB/Simulink
3. 有 Python 或 C++ 编程经验
4. 了解 ROS 机器人操作系统者优先
5. 有飞行器/火箭/无人机相关经验优先
6. 良好的团队协作和文档撰写能力
"""

    analyzer = ResumeAnalyzer()
    result = analyzer.analyze(sample_resume, sample_jd)
    analyzer.report(result)


if __name__ == "__main__":
    main()
