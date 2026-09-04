# -*- coding: utf-8 -*-
"""简历解析：项目经历 / 竞赛与荣誉 / 自我评价 提取（预览页依赖，2026-09-04 修复）。"""
from app.matching.resume_parser import parse_resume

SAMPLE = """姓名：李雷
电话：13800138000
邮箱：lilei@example.com
教育背景
2019.09 - 2023.06 某大学 软件工程 本科
项目经历
智能问答平台 2022.03 - 至今
负责模型服务开发与上线。
竞赛与荣誉
2023.09 全国大学生数学建模竞赛 国家一等奖
校三好学生
自我评价
踏实肯干，责任心强。
学习能力强。
"""

def test_project_name_before_and_after_time():
    r = parse_resume(SAMPLE)
    names = [p.get("name") for p in r["project_experience"]]
    assert "智能问答平台" in names, names


def test_honors_extracted():
    r = parse_resume(SAMPLE)
    titles = [h["title"] for h in r["honors"]]
    assert "全国大学生数学建模竞赛 国家一等奖" in titles
    assert "校三好学生" in titles
    assert r["honors"][0]["time"] == "2023.09"


def test_self_evaluation_merged():
    r = parse_resume(SAMPLE)
    assert "踏实肯干" in r["self_evaluation"]
    assert "学习能力强" in r["self_evaluation"]


def test_project_section_stops_at_honors():
    r = parse_resume(SAMPLE)
    desc = "".join(p.get("description") and "".join(p["description"]) or "" for p in r["project_experience"])
    assert "数学建模" not in desc