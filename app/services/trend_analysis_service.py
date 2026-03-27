from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.db.models.error_reason import ErrorReason
from app.db.models.study_record import StudyRecord
from app.db.models.subject import Subject
from app.db.models.trend_analysis import TrendAnalysis
from app.db.models.wrong_question import WrongQuestion
from app.db.models.wrong_question_error_reason import WrongQuestionErrorReason
from app.db.session import SessionLocal
from app.services.agent_config_service import get_llm_client_for_agent
from app.services.llm_client_service import LlmClientError, get_siliconflow_client


# ---------------------------------------------------------------------------
# LLM Prompt
# ---------------------------------------------------------------------------

TREND_SYSTEM_PROMPT = (
    "你是一位经验丰富的小学教育专家，擅长通过数据分析学生的学习情况。\n"
    "请根据提供的学生错题统计数据，生成一份简洁的学习趋势分析报告。\n"
    "仅返回严格 JSON，格式如下：\n"
    "{\n"
    '  "summary": "整体概述（1-2句话）",\n'
    '  "strengths": ["优势1", "优势2"],\n'
    '  "weaknesses": ["薄弱点1", "薄弱点2"],\n'
    '  "suggestions": ["建议1", "建议2", "建议3"],\n'
    '  "trend_description": "学习趋势描述（正在进步/退步/持平）",\n'
    '  "risk_subjects": ["需要重点关注的学科"],\n'
    '  "score": 0-100\n'
    "}"
)


# ---------------------------------------------------------------------------
# 统计数据收集
# ---------------------------------------------------------------------------


def collect_student_stats(
    db: Session,
    student_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    subject_filter: Optional[str] = None,
) -> dict[str, Any]:
    """收集学生统计快照，用于 LLM 分析。"""

    # --- 基础过滤条件 ---
    wq_filters = [WrongQuestion.student_id == student_id]
    if start_date:
        wq_filters.append(WrongQuestion.first_error_date >= start_date)
    if end_date:
        wq_filters.append(WrongQuestion.first_error_date <= end_date)

    sr_filters = [StudyRecord.student_id == student_id]
    if start_date:
        sr_filters.append(StudyRecord.study_date >= start_date)
    if end_date:
        sr_filters.append(StudyRecord.study_date <= end_date)

    # 如果指定了学科过滤
    if subject_filter:
        subject_obj = db.query(Subject).filter(Subject.code == subject_filter).first()
        if subject_obj:
            wq_filters.append(WrongQuestion.subject_id == subject_obj.id)

    # --- 1. 各学科错题数量和状态分布 ---
    subject_rows = (
        db.query(
            Subject.code.label("subject_code"),
            Subject.name.label("subject_name"),
            func.count(WrongQuestion.id).label("total"),
            func.coalesce(
                func.sum(case((WrongQuestion.status == "new", 1), else_=0)), 0
            ).label("new_count"),
            func.coalesce(
                func.sum(case((WrongQuestion.status == "reviewing", 1), else_=0)), 0
            ).label("reviewing_count"),
            func.coalesce(
                func.sum(case((WrongQuestion.status == "mastered", 1), else_=0)), 0
            ).label("mastered_count"),
        )
        .select_from(WrongQuestion)
        .outerjoin(Subject, WrongQuestion.subject_id == Subject.id)
        .filter(*wq_filters)
        .group_by(Subject.code, Subject.name)
        .all()
    )

    subject_stats = [
        {
            "subject_code": row.subject_code or "unknown",
            "subject_name": row.subject_name or "未分类",
            "total": int(row.total or 0),
            "new": int(row.new_count or 0),
            "reviewing": int(row.reviewing_count or 0),
            "mastered": int(row.mastered_count or 0),
        }
        for row in subject_rows
    ]

    # --- 2. 高频错因 TOP5 ---
    reason_rows = (
        db.query(
            ErrorReason.name.label("reason_name"),
            func.count(WrongQuestionErrorReason.wrong_question_id).label("total"),
        )
        .join(
            WrongQuestionErrorReason,
            WrongQuestionErrorReason.error_reason_id == ErrorReason.id,
        )
        .join(WrongQuestion, WrongQuestion.id == WrongQuestionErrorReason.wrong_question_id)
        .filter(*wq_filters)
        .group_by(ErrorReason.name)
        .order_by(func.count(WrongQuestionErrorReason.wrong_question_id).desc())
        .limit(5)
        .all()
    )

    top_reasons = [
        {"reason": row.reason_name, "count": int(row.total or 0)}
        for row in reason_rows
    ]

    # --- 3. 学习记录趋势（每日做对/做错次数） ---
    trend_rows = (
        db.query(
            StudyRecord.study_date.label("date"),
            func.count(StudyRecord.id).label("total"),
            func.coalesce(
                func.sum(case((StudyRecord.result == "correct", 1), else_=0)), 0
            ).label("correct"),
            func.coalesce(
                func.sum(case((StudyRecord.result == "incorrect", 1), else_=0)), 0
            ).label("incorrect"),
        )
        .filter(*sr_filters)
        .group_by(StudyRecord.study_date)
        .order_by(StudyRecord.study_date.asc())
        .all()
    )

    daily_trend = [
        {
            "date": str(row.date),
            "total": int(row.total or 0),
            "correct": int(row.correct or 0),
            "incorrect": int(row.incorrect or 0),
        }
        for row in trend_rows
    ]

    # --- 4. 整体概要 ---
    total_wrong = db.query(func.count(WrongQuestion.id)).filter(*wq_filters).scalar() or 0
    total_mastered = (
        db.query(func.count(WrongQuestion.id))
        .filter(*wq_filters, WrongQuestion.status == "mastered")
        .scalar()
        or 0
    )
    total_study_records = db.query(func.count(StudyRecord.id)).filter(*sr_filters).scalar() or 0

    return {
        "total_wrong_questions": int(total_wrong),
        "total_mastered": int(total_mastered),
        "total_study_records": int(total_study_records),
        "subject_stats": subject_stats,
        "top_error_reasons": top_reasons,
        "daily_trend": daily_trend,
    }


# ---------------------------------------------------------------------------
# LLM 调用
# ---------------------------------------------------------------------------


def _build_user_prompt(student_id: int, stats: dict[str, Any]) -> str:
    """构建趋势分析的 user prompt。"""
    parts = [
        f"学生ID: {student_id}",
        f"错题总数: {stats['total_wrong_questions']}",
        f"已掌握: {stats['total_mastered']}",
        f"练习记录总数: {stats['total_study_records']}",
        "",
        "## 学科分布",
    ]
    for s in stats["subject_stats"]:
        parts.append(
            f"- {s['subject_name']}: 共{s['total']}题 "
            f"(新增{s['new']}, 复习中{s['reviewing']}, 已掌握{s['mastered']})"
        )

    parts.append("")
    parts.append("## 高频错因 TOP5")
    for r in stats["top_error_reasons"]:
        parts.append(f"- {r['reason']}: {r['count']}次")

    parts.append("")
    parts.append("## 每日学习趋势（最近）")
    # 只取最近 14 天的趋势
    recent_trend = stats["daily_trend"][-14:] if stats["daily_trend"] else []
    for t in recent_trend:
        parts.append(f"- {t['date']}: 练习{t['total']}题, 正确{t['correct']}, 错误{t['incorrect']}")

    if not recent_trend:
        parts.append("- 暂无练习记录")

    return "\n".join(parts)


def _parse_analysis_result(text: str) -> Optional[dict]:
    """解析 LLM 返回的 JSON 结果。"""
    cleaned = text.strip()
    if not cleaned:
        return None

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 对象
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# BackgroundTask 入口
# ---------------------------------------------------------------------------


def run_trend_analysis_task(analysis_id: int) -> None:
    """
    BackgroundTask 入口：执行趋势分析。
    在独立的 DB Session 中运行。
    """
    db = SessionLocal()
    try:
        _execute_analysis(db, analysis_id)
    except Exception:
        logger.exception("run_trend_analysis_task failed for analysis_id=%s", analysis_id)
        # 尝试标记为失败
        try:
            analysis = db.query(TrendAnalysis).filter(TrendAnalysis.id == analysis_id).first()
            if analysis and analysis.status == "running":
                analysis.status = "failed"
                analysis.error_message = "Internal error during analysis"
                analysis.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            logger.exception("Failed to mark analysis as failed")
    finally:
        db.close()


def _execute_analysis(db: Session, analysis_id: int) -> None:
    """实际执行趋势分析逻辑。"""
    analysis = db.query(TrendAnalysis).filter(TrendAnalysis.id == analysis_id).first()
    if not analysis:
        logger.error("TrendAnalysis id=%s not found", analysis_id)
        return

    # 标记为运行中
    analysis.status = "running"
    db.commit()

    try:
        # 1. 收集统计数据
        stats = collect_student_stats(
            db,
            analysis.student_id,
            start_date=analysis.start_date,
            end_date=analysis.end_date,
            subject_filter=analysis.subject_filter,
        )

        # 保存输入快照
        analysis.input_snapshot = json.dumps(stats, ensure_ascii=False)
        db.commit()

        # 2. 构建 prompt
        user_prompt = _build_user_prompt(analysis.student_id, stats)

        # 3. 获取 LLM 客户端
        result = get_llm_client_for_agent(db, "trend_analyze")
        if result:
            client, config = result
            model = config.model
            temperature = config.temperature
        else:
            # 回退到 siliconflow
            sf_client = get_siliconflow_client()
            if not sf_client or not sf_client.default_model:
                raise RuntimeError("No LLM client available for trend analysis")
            client = sf_client.base_client
            model = sf_client.default_model
            temperature = 0.3

        # 4. 调用 LLM
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": TREND_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        body = client.chat_completions(payload, trace_id="trend_analysis")

        content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        # 5. 解析结果
        parsed = _parse_analysis_result(content)
        if parsed:
            analysis.analysis_result = json.dumps(parsed, ensure_ascii=False)
            analysis.status = "completed"
        else:
            # 无法解析为 JSON，存储原始文本
            analysis.analysis_result = json.dumps(
                {"raw_text": content}, ensure_ascii=False
            )
            analysis.status = "completed"

        analysis.completed_at = datetime.utcnow()
        db.commit()

        logger.info("TrendAnalysis id=%s completed successfully", analysis_id)

    except (LlmClientError, RuntimeError) as exc:
        logger.exception("TrendAnalysis id=%s LLM call failed", analysis_id)
        analysis.status = "failed"
        analysis.error_message = str(exc)
        analysis.completed_at = datetime.utcnow()
        db.commit()
