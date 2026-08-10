"""Cluster Discrimination — file 01 mục 2.

    GET /api/clusters/{cluster_id}
    GET /api/clusters/{cluster_id}/practice
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.models.lexical import (
    ConfusionCluster,
    ConfusionClusterMember,
    LexicalItem,
    Sense,
)
from app.schemas.api import ClusterExerciseOut, ClusterOut
from app.services.cluster_service import build_discrimination_exercise

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.get("", response_model=list[ClusterOut])
async def list_clusters(user: CurrentUser, session: SessionDep) -> list[dict]:
    """Ngoài spec nhưng cần thiết: UI phải liệt kê được cluster trước khi mở từng cái."""
    clusters = (
        (
            await session.execute(
                select(ConfusionCluster)
                .where(ConfusionCluster.user_id == user.id)
                .order_by(ConfusionCluster.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [await _cluster_payload(session, c) for c in clusters]


@router.get("/{cluster_id}", response_model=ClusterOut)
async def get_cluster(
    cluster_id: str, user: CurrentUser, session: SessionDep
) -> dict:
    cluster = await session.get(ConfusionCluster, cluster_id)
    if cluster is None or cluster.user_id != user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy cluster")
    return await _cluster_payload(session, cluster)


@router.get("/{cluster_id}/practice", response_model=ClusterExerciseOut)
async def practice(cluster_id: str, user: CurrentUser, session: SessionDep) -> dict:
    """Sinh bài tập chọn từ đúng trong cluster.

    KHÔNG gọi LLM: bài tập được dựng từ ví dụ đã có sẵn trong DB (fast path).
    """
    exercise = await build_discrimination_exercise(session, cluster_id, user.id)
    if exercise is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Chưa dựng được bài tập cho cluster này — cần ít nhất 2 thành viên và "
                "một câu ví dụ có chứa từ mục tiêu."
            ),
        )
    return exercise


async def _cluster_payload(session, cluster: ConfusionCluster) -> dict:
    rows = (
        await session.execute(
            select(
                ConfusionClusterMember.sense_id,
                ConfusionClusterMember.distinguishing_note,
                LexicalItem.surface_form,
                Sense.definition_en,
            )
            .join(Sense, Sense.id == ConfusionClusterMember.sense_id)
            .join(LexicalItem, LexicalItem.id == Sense.lexical_item_id)
            .where(ConfusionClusterMember.cluster_id == cluster.id)
        )
    ).all()
    return {
        "id": cluster.id,
        "cluster_label": cluster.cluster_label,
        "created_at": cluster.created_at,
        "members": [
            {
                "sense_id": sense_id,
                "surface_form": surface_form,
                "definition_en": definition_en,
                "distinguishing_note": note,
            }
            for sense_id, note, surface_form, definition_en in rows
        ],
    }
