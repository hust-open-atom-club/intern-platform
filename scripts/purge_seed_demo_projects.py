#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""删除历史上 seed 写入的演示课题及其申请（不影响社区与登录账号）。"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import delete, or_, select

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from intern_platform.db.session import SessionLocal
from intern_platform.models.announcement import Announcement
from intern_platform.models.application import Application
from intern_platform.models.application_message import ApplicationMessage
from intern_platform.models.cooperation_case import CooperationCase
from intern_platform.models.final_submission import FinalSubmission
from intern_platform.models.liaison_message import LiaisonMessage
from intern_platform.models.mentor_update_seen import MentorUpdateSeen
from intern_platform.models.notification import Notification
from intern_platform.models.project import Project
from intern_platform.models.review_record import ReviewRecord

SEED_TITLES = {
    "SpMV 开源实习演示项目",
    "镜像同步策略优化",
    "俱乐部贡献指南改版",
    "实习平台本地一键启动脚本",
    "开源模型推理示例工程",
    "稀疏矩阵向量乘（SpMV）算子优化",
    "openGauss 新手贡献指南整理",
    "昇思框架推理示例补全",
    "RT-Thread 组件文档与示例补全",
}


def purge() -> None:
    session = SessionLocal()
    try:
        projects = session.scalars(
            select(Project).where(
                or_(
                    Project.title.in_(SEED_TITLES),
                    Project.repo_url.like("%/demo/%"),
                    Project.repo_url.like("%git.hust.openatom.club/demo%"),
                )
            )
        ).all()
        if not projects:
            print("purge_seed_demo_projects: nothing to delete")
            return

        project_ids = [p.id for p in projects]
        apps = session.scalars(
            select(Application).where(Application.project_id.in_(project_ids))
        ).all()
        app_ids = [a.id for a in apps]
        print(
            "deleting projects:",
            [(p.id, p.title) for p in projects],
            "applications:",
            app_ids,
        )

        if app_ids:
            session.execute(
                delete(MentorUpdateSeen).where(MentorUpdateSeen.application_id.in_(app_ids))
            )
            session.execute(
                delete(ApplicationMessage).where(ApplicationMessage.application_id.in_(app_ids))
            )
            session.execute(delete(ReviewRecord).where(ReviewRecord.application_id.in_(app_ids)))
            session.execute(
                delete(FinalSubmission).where(FinalSubmission.application_id.in_(app_ids))
            )
            session.execute(
                delete(CooperationCase).where(CooperationCase.application_id.in_(app_ids))
            )
            session.execute(
                delete(LiaisonMessage).where(LiaisonMessage.application_id.in_(app_ids))
            )
            session.execute(delete(Notification).where(Notification.application_id.in_(app_ids)))
            session.execute(delete(Announcement).where(Announcement.application_id.in_(app_ids)))
            session.execute(delete(Application).where(Application.id.in_(app_ids)))

        session.execute(delete(Notification).where(Notification.project_id.in_(project_ids)))
        session.execute(delete(Announcement).where(Announcement.project_id.in_(project_ids)))
        session.execute(delete(Project).where(Project.id.in_(project_ids)))
        session.commit()
        print(f"purge_ok removed_projects={len(project_ids)} removed_apps={len(app_ids)}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    purge()
