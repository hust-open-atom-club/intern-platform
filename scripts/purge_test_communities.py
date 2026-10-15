#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""删除云端 e2e/安全探测留下的测试社区；保留种子社区与 openmin。

用法:
  python scripts/purge_test_communities.py           # dry-run
  python scripts/purge_test_communities.py --apply   # 真正删除
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from intern_platform.db.session import SessionLocal
from intern_platform.models.announcement import Announcement
from intern_platform.models.application import Application
from intern_platform.models.application_message import ApplicationMessage
from intern_platform.models.community import Community
from intern_platform.models.community_extension import CommunityExtension
from intern_platform.models.cooperation_case import CooperationCase
from intern_platform.models.final_submission import FinalSubmission
from intern_platform.models.liaison_message import LiaisonMessage
from intern_platform.models.mentor_update_seen import MentorUpdateSeen
from intern_platform.models.notification import Notification
from intern_platform.models.project import Project
from intern_platform.models.review_record import ReviewRecord
from intern_platform.models.role import UserRole

# 正式种子 + 真实拆分组织
KEEP_SLUGS = {
    "kernel",
    "mirror",
    "docs",
    "devtools",
    "ai-lab",
    "openeuler",
    "opengauss",
    "mindspore",
    "rtthread",
    "openmin",
}

# 这些学生的进行中申请所在社区一律跳过（防误伤）
PROTECT_STUDENT_EMAILS = {
    "feizi_050920@qq.com",
}


def _app_ids_for_community(session, community_id: int) -> list[int]:
    project_ids = list(
        session.scalars(select(Project.id).where(Project.community_id == community_id)).all()
    )
    if not project_ids:
        return []
    return list(
        session.scalars(
            select(Application.id).where(Application.project_id.in_(project_ids))
        ).all()
    )


def _has_protected_apps(session, community_id: int) -> bool:
    from intern_platform.models.user import User

    project_ids = list(
        session.scalars(select(Project.id).where(Project.community_id == community_id)).all()
    )
    if not project_ids:
        return False
    hit = session.scalar(
        select(Application.id)
        .join(User, User.id == Application.student_id)
        .where(
            Application.project_id.in_(project_ids),
            User.email.in_(PROTECT_STUDENT_EMAILS),
            Application.status.notin_(("draft", "withdrawn", "rejected")),
        )
        .limit(1)
    )
    return hit is not None


def _delete_community(session, community_id: int) -> dict[str, int]:
    project_ids = list(
        session.scalars(select(Project.id).where(Project.community_id == community_id)).all()
    )
    app_ids = _app_ids_for_community(session, community_id)
    counts = {
        "apps": len(app_ids),
        "projects": len(project_ids),
    }
    if app_ids:
        session.execute(delete(MentorUpdateSeen).where(MentorUpdateSeen.application_id.in_(app_ids)))
        session.execute(
            delete(ApplicationMessage).where(ApplicationMessage.application_id.in_(app_ids))
        )
        session.execute(delete(ReviewRecord).where(ReviewRecord.application_id.in_(app_ids)))
        session.execute(delete(FinalSubmission).where(FinalSubmission.application_id.in_(app_ids)))
        session.execute(delete(CooperationCase).where(CooperationCase.application_id.in_(app_ids)))
        session.execute(delete(LiaisonMessage).where(LiaisonMessage.application_id.in_(app_ids)))
        session.execute(delete(Notification).where(Notification.application_id.in_(app_ids)))
        session.execute(delete(Announcement).where(Announcement.application_id.in_(app_ids)))
        session.execute(delete(Application).where(Application.id.in_(app_ids)))
    if project_ids:
        session.execute(delete(Notification).where(Notification.project_id.in_(project_ids)))
        session.execute(delete(Announcement).where(Announcement.project_id.in_(project_ids)))
        session.execute(delete(Project).where(Project.id.in_(project_ids)))
    session.execute(delete(LiaisonMessage).where(LiaisonMessage.community_id == community_id))
    session.execute(delete(CooperationCase).where(CooperationCase.community_id == community_id))
    session.execute(delete(Announcement).where(Announcement.community_id == community_id))
    session.execute(
        delete(CommunityExtension).where(CommunityExtension.community_id == community_id)
    )
    session.execute(delete(UserRole).where(UserRole.community_id == community_id))
    session.execute(delete(Community).where(Community.id == community_id))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="真正删除；默认只 dry-run")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        rows = session.scalars(select(Community).order_by(Community.id)).all()
        keep: list[dict] = []
        delete_list: list[dict] = []
        skip_protected: list[dict] = []
        for cm in rows:
            item = {
                "id": cm.id,
                "name": cm.name,
                "slug": cm.slug,
                "status": cm.status,
            }
            if cm.slug in KEEP_SLUGS:
                keep.append(item)
                continue
            if _has_protected_apps(session, cm.id):
                skip_protected.append(item)
                continue
            delete_list.append(item)

        report = {
            "mode": "apply" if args.apply else "dry-run",
            "keep": keep,
            "skip_protected": skip_protected,
            "delete": delete_list,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))

        if not args.apply:
            print(f"dry_run_ok would_delete={len(delete_list)} keep={len(keep)}")
            return

        removed = []
        for item in delete_list:
            counts = _delete_community(session, item["id"])
            removed.append({**item, **counts})
        session.commit()
        print(json.dumps({"removed": removed}, ensure_ascii=False, indent=2))
        print(f"purge_test_communities_ok deleted={len(removed)}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
