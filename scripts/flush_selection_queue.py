"""将滞留在 community_review / committee_review 的申请推进到 selected。

去掉组织端「选拔审核」后，历史单不会再被社区点通过；部署后跑一次即可。
用法（容器内）:
  python scripts/flush_selection_queue.py
"""

from __future__ import annotations

from sqlalchemy import select

from intern_platform.db.session import SessionLocal
from intern_platform.models.application import Application
from intern_platform.services.application_workflow import (
    ApplicationWorkflowService,
    TransitionContext,
)


def main() -> None:
    session = SessionLocal()
    wf = ApplicationWorkflowService(session)
    rows = list(
        session.scalars(
            select(Application).where(
                Application.status.in_(("community_review", "committee_review"))
            )
        ).all()
    )
    print(f"stuck={len(rows)}")
    ok = 0
    for app in rows:
        try:
            actions = (
                ["approve_community", "approve_committee"]
                if app.status == "community_review"
                else ["approve_committee"]
            )
            for idx, action in enumerate(actions):
                wf.transition(
                    app,
                    TransitionContext(
                        actor_id=0,
                        action=action,
                        actor_role="system",
                        comment="系统：取消社区选拔审核后自动计入中选",
                        request_id=f"flush-sel-{app.id}-{idx}",
                        correlation_id=f"flush-sel-{app.id}",
                        idempotency_key=f"flush-sel-{app.id}-{action}-v{app.version}",
                        trace_id=f"flush-sel-{app.id}",
                    ),
                )
            session.commit()
            ok += 1
            print(f"  app#{app.id} -> {app.status}")
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            print(f"  app#{app.id} FAIL {exc}")
    print(f"done ok={ok}/{len(rows)}")
    session.close()


if __name__ == "__main__":
    main()
