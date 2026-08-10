"""Seed dữ liệu demo để xem giao diện với nội dung thật.

    docker compose exec backend python -m scripts.seed_demo

Tạo tài khoản demo@vf.local / secret123 kèm:
  - 10 collocation học thuật có nghĩa, ví dụ theo dạng bài IELTS, mẹo nhớ
  - một confusion cluster (significant / substantial / considerable)
  - lịch sử review 20 ngày để retention, streak, error breakdown và leech có số liệu

KHÔNG gọi LLM: dữ liệu viết tay, chỉ để dựng UI. Chạy lại nhiều lần thì xoá tài khoản
cũ rồi tạo lại.
"""

from __future__ import annotations

import asyncio
import random
from datetime import timedelta

from sqlalchemy import delete, select

from app.core.db import AsyncSessionLocal, init_db
from app.core.security import hash_password
from app.core.time import to_iso, utcnow
from app.models.jobs import IngestionCandidate, IngestionJob
from app.models.lexical import (
    ConfusionCluster,
    ConfusionClusterMember,
    ExampleSentence,
    LexicalItem,
    Mnemonic,
    Sense,
)
from app.models.production import ProductionAttempt
from app.models.srs import Card, ReviewLog
from app.models.user import Deck, User

EMAIL = "demo@vf.local"
PASSWORD = "secret123"

# (surface_form, item_type, cefr, definition_en, definition_vi, pos, register, [(câu, essay_type)], mnemonic|None)
WORDS = [
    (
        "have a detrimental effect on",
        "collocation",
        "C1",
        "to cause harm or damage to something over time",
        "gây tác động tiêu cực tới",
        "verb phrase",
        "academic",
        [
            (
                "Excessive screen time among teenagers has a detrimental effect on both their sleep quality and academic performance.",
                "opinion",
            ),
            (
                "Unregulated industrial expansion has a detrimental effect on the air quality of surrounding residential districts.",
                "problem_solution",
            ),
        ],
        "detrimental nghe như 'đe doạ mental' — hình dung màn hình phát sáng lúc 2 giờ sáng đang bào mòn não bạn từng chút một.",
    ),
    (
        "address a concern",
        "collocation",
        "B2",
        "to deal with a worry or problem that people have raised",
        "giải quyết một mối lo ngại",
        "verb phrase",
        "academic",
        [
            (
                "Governments must address this concern before public trust in the healthcare system erodes any further.",
                "problem_solution",
            ),
            (
                "Universities have been slow to address concerns about the mental health of international students.",
                "discussion",
            ),
        ],
        None,
    ),
    (
        "make a substantial contribution",
        "collocation",
        "C1",
        "to add something important and valuable to a result",
        "đóng góp đáng kể",
        "verb phrase",
        "academic",
        [
            (
                "Immigrant workers make a substantial contribution to the economies of the countries that receive them.",
                "advantage_disadvantage",
            ),
        ],
        None,
    ),
    (
        "a significant increase in",
        "collocation",
        "B2",
        "a rise large enough to be noticed and measured",
        "sự gia tăng đáng kể",
        "noun phrase",
        "academic",
        [
            (
                "The past decade has seen a significant increase in the number of households relying on food banks.",
                "discussion",
            ),
        ],
        None,
    ),
    (
        "attract considerable attention",
        "collocation",
        "C1",
        "to make a lot of people notice and discuss something",
        "thu hút sự chú ý đáng kể",
        "verb phrase",
        "academic",
        [
            (
                "The proposal to shorten the working week has attracted considerable attention from both economists and labour unions.",
                "opinion",
            ),
        ],
        None,
    ),
    (
        "pose a threat to",
        "collocation",
        "B2",
        "to be likely to cause harm or danger to something",
        "đặt ra mối đe doạ đối với",
        "verb phrase",
        "academic",
        [
            (
                "Rising sea levels pose a serious threat to low-lying coastal communities across Southeast Asia.",
                "problem_solution",
            ),
        ],
        None,
    ),
    (
        "exacerbate the problem",
        "collocation",
        "C1",
        "to make a bad situation even worse",
        "làm trầm trọng thêm vấn đề",
        "verb phrase",
        "academic",
        [
            (
                "Building wider roads often exacerbates the problem of urban congestion rather than relieving it.",
                "problem_solution",
            ),
        ],
        "exacerbate — gốc Latin 'acerbus' nghĩa là chua/gắt (cùng gốc với 'acerbic'). Thêm chua vào món đã hỏng: làm mọi thứ tệ hơn.",
    ),
    (
        "mitigate the impact of",
        "collocation",
        "C1",
        "to reduce how bad the effects of something are",
        "giảm nhẹ tác động của",
        "verb phrase",
        "academic",
        [
            (
                "Planting urban forests can mitigate the impact of heatwaves on densely populated city centres.",
                "problem_solution",
            ),
        ],
        "mitigate ~ 'my tí gọt' — bạn gọt bớt phần nhọn của một tảng đá đang lăn xuống, nó vẫn lăn nhưng đỡ đau hơn.",
    ),
    (
        "undermine confidence in",
        "collocation",
        "C1",
        "to gradually weaken people's trust in something",
        "làm suy giảm niềm tin vào",
        "verb phrase",
        "academic",
        [
            (
                "Repeated policy reversals undermine public confidence in the government's ability to plan for the long term.",
                "discussion",
            ),
        ],
        "under + mine: đào hầm NGẦM BÊN DƯỚI một toà lâu đài. Bên ngoài vẫn nguyên vẹn, nhưng nền đã rỗng và nó sẽ sập.",
    ),
    (
        "a viable alternative",
        "collocation",
        "C1",
        "another choice that is realistic and can actually work",
        "một lựa chọn thay thế khả thi",
        "noun phrase",
        "academic",
        [
            (
                "For many commuters, cycling is not yet a viable alternative to driving because the infrastructure remains inadequate.",
                "advantage_disadvantage",
            ),
        ],
        None,
    ),
]

# Nhóm cận nghĩa để trang Phân tích và thẻ cluster_discrimination có nội dung.
CLUSTER = {
    "label": "Tính từ mức độ: diễn đạt 'lớn / đáng kể'",
    "members": {
        "a significant increase in": "dùng với số liệu ĐO ĐƯỢC và đủ lớn để không phải ngẫu nhiên, vd 'a significant increase in crime rates'",
        "make a substantial contribution": "nhấn vào KHỐI LƯỢNG/giá trị thực chất, thường đi với danh từ trừu tượng, vd 'a substantial contribution to society'",
        "attract considerable attention": "nhấn vào MỨC ĐỘ nhiều, trang trọng hơn 'a lot of', thường đi với danh từ không đếm được, vd 'considerable attention'",
    },
}


async def main() -> None:
    await init_db()
    random.seed(7)
    now = utcnow()

    async with AsyncSessionLocal() as session:
        # --- Xoá tài khoản demo cũ (chạy lại được nhiều lần) ---
        old = (
            await session.execute(select(User).where(User.email == EMAIL))
        ).scalar_one_or_none()
        if old is not None:
            card_ids = list(
                (
                    await session.execute(select(Card.id).where(Card.user_id == old.id))
                ).scalars()
            )
            if card_ids:
                await session.execute(
                    delete(ProductionAttempt).where(
                        ProductionAttempt.card_id.in_(card_ids)
                    )
                )
                await session.execute(
                    delete(ReviewLog).where(ReviewLog.card_id.in_(card_ids))
                )
            cluster_ids = list(
                (
                    await session.execute(
                        select(ConfusionCluster.id).where(
                            ConfusionCluster.user_id == old.id
                        )
                    )
                ).scalars()
            )
            if cluster_ids:
                await session.execute(
                    delete(ConfusionClusterMember).where(
                        ConfusionClusterMember.cluster_id.in_(cluster_ids)
                    )
                )
                await session.execute(
                    delete(ConfusionCluster).where(ConfusionCluster.id.in_(cluster_ids))
                )
            await session.execute(delete(Card).where(Card.user_id == old.id))
            job_ids = list(
                (
                    await session.execute(
                        select(IngestionJob.id).where(IngestionJob.user_id == old.id)
                    )
                ).scalars()
            )
            if job_ids:
                await session.execute(
                    delete(IngestionCandidate).where(
                        IngestionCandidate.job_id.in_(job_ids)
                    )
                )
                await session.execute(
                    delete(IngestionJob).where(IngestionJob.id.in_(job_ids))
                )
            await session.execute(delete(Deck).where(Deck.user_id == old.id))
            await session.delete(old)
            await session.commit()

        user = User(
            email=EMAIL,
            password_hash=hash_password(PASSWORD),
            daily_new_word_goal=15,
            timezone="Asia/Ho_Chi_Minh",
        )
        session.add(user)
        await session.flush()

        deck = Deck(
            user_id=user.id,
            name="IELTS Academic Reading",
            description="Collocation trích từ bài đọc thật",
        )
        session.add(deck)
        await session.flush()

        sense_by_form: dict[str, str] = {}

        for position, (
            surface,
            item_type,
            cefr,
            definition_en,
            definition_vi,
            pos,
            register,
            examples,
            mnemonic,
        ) in enumerate(WORDS):
            item = LexicalItem(
                surface_form=surface,
                item_type=item_type,
                cefr_level=cefr,
                source_deck_id=deck.id,
            )
            session.add(item)
            await session.flush()

            sense = Sense(
                lexical_item_id=item.id,
                definition_en=definition_en,
                definition_vi=definition_vi,
                part_of_speech=pos,
                register=register,
            )
            session.add(sense)
            await session.flush()
            sense_by_form[surface] = sense.id

            for index, (sentence, essay_type) in enumerate(examples):
                session.add(
                    ExampleSentence(
                        sense_id=sense.id,
                        sentence=sentence,
                        essay_type=essay_type,
                        # Câu đầu coi như lấy từ chính bài đọc của người học.
                        source="user_reading" if index == 0 else "agent_generated",
                        generated_by_model=None if index == 0 else "deepseek-chat",
                    )
                )
            if mnemonic:
                session.add(
                    Mnemonic(
                        sense_id=sense.id,
                        mnemonic_text=mnemonic,
                        mnemonic_type="etymology"
                        if "gốc Latin" in mnemonic or "under + mine" in mnemonic
                        else "keyword_dual_coding",
                        generated_by_model="deepseek-chat",
                    )
                )

            # --- Trạng thái thẻ trải đều để vệt bút dạ có đủ các mức độ ---
            # 3 từ đầu đã chín (stability cao), giữa là đang học, cuối là thẻ mới.
            for direction in ("en_to_vi", "vi_to_en", "production"):
                if position < 4:
                    state, stability, difficulty = "review", 8.0 + position * 9.5, 4.5
                    reps, lapses = 6 + position, 1 if position == 1 else 0
                    last = now - timedelta(days=2 + position)
                    due = now + timedelta(days=stability * 0.6)
                elif position < 7:
                    state, stability, difficulty = "learning", 1.4 + position * 0.3, 6.2
                    reps, lapses = 2, 0
                    last = now - timedelta(hours=20)
                    due = now - timedelta(minutes=30)  # đến hạn ngay
                else:
                    state, stability, difficulty = "new", 0.0, 0.0
                    reps, lapses = 0, 0
                    last, due = None, now

                session.add(
                    Card(
                        sense_id=sense.id,
                        user_id=user.id,
                        card_direction=direction,
                        state=state,
                        stability=stability,
                        difficulty=difficulty,
                        due_at=to_iso(due),
                        last_reviewed_at=to_iso(last),
                        reps=reps,
                        lapses=lapses,
                        is_leech=False,
                        learning_step=None if state == "review" else 1,
                    )
                )

        await session.flush()

        # --- Cluster cận nghĩa ---
        cluster = ConfusionCluster(user_id=user.id, cluster_label=CLUSTER["label"])
        session.add(cluster)
        await session.flush()
        for form, note in CLUSTER["members"].items():
            session.add(
                ConfusionClusterMember(
                    cluster_id=cluster.id,
                    sense_id=sense_by_form[form],
                    distinguishing_note=note,
                )
            )
            session.add(
                Card(
                    sense_id=sense_by_form[form],
                    user_id=user.id,
                    card_direction="cluster_discrimination",
                    state="learning",
                    stability=2.5,
                    difficulty=6.0,
                    due_at=to_iso(now - timedelta(minutes=5)),
                    last_reviewed_at=to_iso(now - timedelta(days=1)),
                    reps=1,
                    lapses=0,
                    learning_step=1,
                )
            )

        # --- Một thẻ leech + mnemonic đã được sinh lại (khác Anki: không ẩn thẻ) ---
        leech_sense = sense_by_form["exacerbate the problem"]
        leech_card = (
            await session.execute(
                select(Card).where(
                    Card.sense_id == leech_sense, Card.card_direction == "en_to_vi"
                )
            )
        ).scalar_one()
        leech_card.is_leech = True
        leech_card.lapses = 9
        leech_card.reps = 17
        session.add(
            Mnemonic(
                sense_id=leech_sense,
                mnemonic_text="Cách khác: hình dung một vết nứt trên tường, bạn cầm búa gõ thêm — 'ex-ACERBA-te' nghe như tiếng búa gõ vào chỗ đã hỏng.",
                mnemonic_type="story_link",
                generated_by_model="deepseek-chat",
            )
        )

        await session.flush()

        # --- Lịch sử review 20 ngày: đủ để có retention, streak, error breakdown ---
        cards = list(
            (
                await session.execute(
                    select(Card).where(
                        Card.user_id == user.id, Card.state.in_(("review", "learning"))
                    )
                )
            ).scalars()
        )
        error_pool = [None, None, None, "collocation", "meaning", "spelling", "register"]
        for day_offset in range(20, -1, -1):
            # Bỏ 2 ngày ở giữa để chuỗi ngày trông tự nhiên, không phải đường thẳng.
            if day_offset in (11, 12):
                continue
            reviewed_at = now - timedelta(days=day_offset, hours=random.randint(0, 6))
            for card in random.sample(cards, k=min(len(cards), random.randint(4, 9))):
                # ~88% nhớ được → retention hiển thị ở mức thực tế của người học tốt.
                rating = random.choices([1, 2, 3, 4], weights=[12, 18, 55, 15])[0]
                error_type = random.choice(error_pool) if rating <= 2 else None
                session.add(
                    ReviewLog(
                        card_id=card.id,
                        reviewed_at=to_iso(reviewed_at),
                        rating=rating,
                        elapsed_days=round(random.uniform(1.0, 9.0), 2),
                        # >= 1 ngày để lượt này được tính vào retention
                        # (xem MIN_SCHEDULED_DAYS_FOR_RETENTION).
                        scheduled_days=round(random.uniform(1.0, 12.0), 2),
                        error_type=error_type,
                    )
                )

        # --- Vài lần chấm bài viết đã có kết quả ---
        production_cards = list(
            (
                await session.execute(
                    select(Card)
                    .where(Card.user_id == user.id, Card.card_direction == "production")
                    .limit(3)
                )
            ).scalars()
        )
        attempts = [
            (
                "Too much screen time is detrimental for teenagers.",
                False,
                "collocation",
                'Đúng nghĩa rồi, nhưng cụm này đi với "to" chứ không phải "for": "detrimental to teenagers".',
                "Too much screen time is detrimental to teenagers.",
            ),
            (
                "The government should address this concern as soon as possible.",
                True,
                "none",
                "Câu dùng đúng collocation và đúng văn phong academic. Giữ nguyên cách viết này.",
                None,
            ),
            (
                "Migrant workers do a big contribution for the economy.",
                False,
                "collocation",
                'Sai động từ và giới từ đi kèm: phải là "make a substantial contribution to", không phải "do ... for".',
                "Migrant workers make a substantial contribution to the economy.",
            ),
        ]
        for card, (sentence, correct, error_type, feedback, corrected) in zip(
            production_cards, attempts
        ):
            session.add(
                ProductionAttempt(
                    card_id=card.id,
                    user_sentence=sentence,
                    submitted_at=to_iso(now - timedelta(days=random.randint(1, 6))),
                    is_correct=correct,
                    error_type=error_type,
                    feedback_text=feedback,
                    corrected_sentence=corrected,
                    graded_by_model="deepseek-chat",
                    graded_at=to_iso(now - timedelta(days=1)),
                )
            )

        await session.commit()

    print(f"Đã seed xong.\n  email:    {EMAIL}\n  password: {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
