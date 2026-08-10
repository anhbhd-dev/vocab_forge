"""Confusion cluster: tiền lọc similarity → Agent 3 → ghi cluster + card luyện tập.

File 03, Agent 3 + ghi chú kỹ thuật; file 03 mục 6 ("chạy theo batch định kỳ, vd mỗi
khi có >= 5 sense mới, không chạy per-item vì cần so sánh chéo toàn deck").
"""

from __future__ import annotations

import logging
import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentSchemaError, LLMError
from app.agents.cluster_agent import ClusterAgent
from app.core.config import settings
from app.models.lexical import (
    ConfusionCluster,
    ConfusionClusterMember,
    ExampleSentence,
    LexicalItem,
    Sense,
)
from app.models.srs import Card
from app.schemas.agent_io import ClusterCandidateSense, ClusterInput
from app.services.card_factory import create_cards_for_sense
from app.services.similarity import SenseVector, group_similar_senses

logger = logging.getLogger(__name__)


async def _user_senses(session: AsyncSession, user_id: str) -> list[SenseVector]:
    rows = (
        await session.execute(
            select(Sense.id, LexicalItem.surface_form, Sense.definition_en)
            .join(LexicalItem, LexicalItem.id == Sense.lexical_item_id)
            .join(Card, Card.sense_id == Sense.id)
            .where(Card.user_id == user_id)
            .distinct()
        )
    ).all()
    return [SenseVector(sense_id=r[0], surface_form=r[1], definition_en=r[2]) for r in rows]


async def _already_clustered(session: AsyncSession, user_id: str) -> set[str]:
    rows = (
        await session.execute(
            select(ConfusionClusterMember.sense_id)
            .join(
                ConfusionCluster,
                ConfusionCluster.id == ConfusionClusterMember.cluster_id,
            )
            .where(ConfusionCluster.user_id == user_id)
        )
    ).scalars()
    return set(rows)


async def maybe_run_cluster_batch(session: AsyncSession, user_id: str) -> int:
    """Chạy Cluster Agent nếu có đủ sense CHƯA được gom cụm.

    Trả về số cluster mới tạo. Không raise ra ngoài: cluster là tính năng phụ trợ,
    lỗi ở đây không được làm hỏng cả job enrichment.
    """
    senses = await _user_senses(session, user_id)
    clustered = await _already_clustered(session, user_id)
    unclustered = [s for s in senses if s.sense_id not in clustered]

    if len(unclustered) < settings.cluster_min_new_senses:
        return 0

    # Tiền lọc rẻ tiền: chỉ nhóm nào vượt ngưỡng similarity mới được gửi cho LLM.
    # So sánh trên TOÀN BỘ sense của user (không chỉ sense mới) vì từ mới có thể cận
    # nghĩa với từ cũ; nhưng chỉ chạy khi có đủ sense mới để không gọi LLM liên tục.
    groups = group_similar_senses(
        senses, threshold=settings.cluster_similarity_threshold
    )
    groups = [g for g in groups if any(s.sense_id not in clustered for s in g)]
    if not groups:
        return 0

    created = 0
    for group in groups:
        try:
            result = await ClusterAgent().run(
                session,
                ClusterInput(
                    candidate_senses=[
                        ClusterCandidateSense(
                            sense_id=s.sense_id,
                            surface_form=s.surface_form,
                            definition_en=s.definition_en,
                        )
                        for s in group
                    ]
                ),
            )
        except (LLMError, AgentSchemaError) as exc:
            logger.warning("Cluster Agent lỗi: %s", exc)
            continue

        valid_ids = {s.sense_id for s in group}
        for cluster_item in result.output.clusters:
            members = [m for m in cluster_item.members if m.sense_id in valid_ids]
            # Agent được yêu cầu chỉ gom từ THỰC SỰ dễ nhầm — cụm 1 phần tử thì vô
            # nghĩa cho bài tập phân biệt, bỏ qua.
            if len(members) < 2:
                continue

            cluster = ConfusionCluster(
                user_id=user_id, cluster_label=cluster_item.cluster_label
            )
            session.add(cluster)
            await session.flush()

            for member in members:
                session.add(
                    ConfusionClusterMember(
                        cluster_id=cluster.id,
                        sense_id=member.sense_id,
                        distinguishing_note=member.distinguishing_note,
                    )
                )
                # Sense nằm trong cluster mới có card luyện phân biệt (file 01 mục 3).
                await create_cards_for_sense(
                    session,
                    member.sense_id,
                    user_id,
                    directions=("cluster_discrimination",),
                )
            created += 1

    await session.flush()
    return created


async def build_discrimination_exercise(
    session: AsyncSession, cluster_id: str, user_id: str, rng: random.Random | None = None
) -> dict | None:
    """Sinh bài tập điền-từ-vào-chỗ-trống từ dữ liệu ĐÃ CÓ trong DB.

    KHÔNG gọi LLM: câu hỏi được tạo bằng cách lấy một ví dụ có sẵn của một thành viên
    trong cluster rồi khoét chỗ trống. Đây là endpoint nằm trong vòng review nên phải
    theo nguyên tắc fast path (file 00 mục 4.1).
    """
    rng = rng or random.Random()

    cluster = await session.get(ConfusionCluster, cluster_id)
    if cluster is None or cluster.user_id != user_id:
        return None

    rows = (
        await session.execute(
            select(
                ConfusionClusterMember.sense_id,
                ConfusionClusterMember.distinguishing_note,
                LexicalItem.surface_form,
            )
            .join(Sense, Sense.id == ConfusionClusterMember.sense_id)
            .join(LexicalItem, LexicalItem.id == Sense.lexical_item_id)
            .where(ConfusionClusterMember.cluster_id == cluster_id)
        )
    ).all()
    if len(rows) < 2:
        return None

    candidates = list(rows)
    rng.shuffle(candidates)

    for sense_id, note, surface_form in candidates:
        sentence = (
            await session.execute(
                select(ExampleSentence.sentence)
                .where(ExampleSentence.sense_id == sense_id)
                .order_by(func.random())
                .limit(1)
            )
        ).scalar_one_or_none()
        if not sentence:
            continue

        blanked = _blank_out(sentence, surface_form)
        if blanked is None:
            continue

        return {
            "cluster_id": cluster_id,
            "cluster_label": cluster.cluster_label,
            "question_sentence": blanked,
            "correct_sense_id": sense_id,
            "options": [
                {"sense_id": sid, "surface_form": sf} for sid, _n, sf in rows
            ],
            "explanation": note,
        }
    return None


def _blank_out(sentence: str, surface_form: str) -> str | None:
    """Thay cụm mục tiêu trong câu bằng '_____' (không phân biệt hoa thường)."""
    lowered = sentence.lower()
    target = surface_form.lower()
    index = lowered.find(target)
    if index == -1:
        # Thử khớp theo từ chính (từ dài nhất trong cụm) — collocation trong câu thật
        # thường bị chia cắt bởi tân ngữ, vd "have a significant effect on".
        head = max(surface_form.split(), key=len, default="")
        if len(head) < 4:
            return None
        index = lowered.find(head.lower())
        if index == -1:
            return None
        return sentence[:index] + "_____" + sentence[index + len(head) :]
    return sentence[:index] + "_____" + sentence[index + len(surface_form) :]
