"""Decks & Lexical Items — file 01 mục 2.

    GET    /api/decks
    POST   /api/decks
    GET    /api/decks/{deck_id}/items
    POST   /api/lexical-items      # thêm thủ công, trigger enrichment agent
    GET    /api/lexical-items/{id}
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.models.lexical import ExampleSentence, LexicalItem, Mnemonic, Sense
from app.models.srs import Card
from app.models.user import Deck
from app.schemas.api import (
    DeckCreate,
    DeckOut,
    LexicalItemCreate,
    LexicalItemDetail,
    LexicalItemOut,
)
from app.services.ingestion_pipeline import run_enrichment_job
from app.services.tts import audio_url_for

router = APIRouter(tags=["decks"])


@router.get("/api/decks", response_model=list[DeckOut])
async def list_decks(user: CurrentUser, session: SessionDep) -> list[Deck]:
    rows = (
        await session.execute(
            select(Deck).where(Deck.user_id == user.id).order_by(Deck.created_at)
        )
    ).scalars()
    return list(rows)


@router.post("/api/decks", response_model=DeckOut, status_code=201)
async def create_deck(
    payload: DeckCreate, user: CurrentUser, session: SessionDep
) -> Deck:
    deck = Deck(user_id=user.id, name=payload.name, description=payload.description)
    session.add(deck)
    await session.commit()
    await session.refresh(deck)
    return deck


async def _owned_deck(session, user, deck_id: str) -> Deck:
    deck = await session.get(Deck, deck_id)
    if deck is None or deck.user_id != user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy deck")
    return deck


@router.get("/api/decks/{deck_id}/items", response_model=list[LexicalItemOut])
async def deck_items(
    deck_id: str, user: CurrentUser, session: SessionDep
) -> list[LexicalItem]:
    await _owned_deck(session, user, deck_id)
    rows = (
        await session.execute(
            select(LexicalItem)
            .where(LexicalItem.source_deck_id == deck_id)
            .order_by(LexicalItem.created_at)
        )
    ).scalars()
    return list(rows)


@router.post("/api/lexical-items", status_code=202)
async def create_lexical_item(
    payload: LexicalItemCreate,
    user: CurrentUser,
    session: SessionDep,
    background: BackgroundTasks,
) -> dict:
    """Thêm thủ công 1 từ/cụm rồi chạy enrichment agent NỀN.

    Trả 202 kèm `lexical_item_id`: sense/example/mnemonic/cards được sinh bất đồng bộ
    (vòng agent, file 00 mục 4.3), client poll `GET /api/lexical-items/{id}`.
    """
    if payload.deck_id:
        await _owned_deck(session, user, payload.deck_id)

    item = LexicalItem(
        surface_form=payload.surface_form.strip(),
        item_type=payload.item_type,
        source_deck_id=payload.deck_id,
    )
    session.add(item)
    await session.commit()

    background.add_task(
        run_enrichment_job, None, user.id, [item.id], payload.target_ielts_band
    )
    return {
        "lexical_item_id": item.id,
        "status": "enriching",
        "message": "Đang sinh nghĩa/ví dụ/mnemonic ở nền, poll GET /api/lexical-items/{id}",
    }


@router.get("/api/lexical-items/{item_id}", response_model=LexicalItemDetail)
async def get_lexical_item(
    item_id: str, user: CurrentUser, session: SessionDep
) -> dict:
    item = await session.get(LexicalItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lexical item")

    senses = (
        (
            await session.execute(
                select(Sense).where(Sense.lexical_item_id == item_id)
            )
        )
        .scalars()
        .all()
    )

    # Chỉ chủ sở hữu mới xem được: quyền sở hữu suy ra từ card của user trên các sense
    # (lexical_items dùng chung được giữa các user để tái sử dụng dữ liệu agent).
    if senses:
        owns = (
            await session.execute(
                select(Card.id)
                .where(
                    Card.user_id == user.id,
                    Card.sense_id.in_([s.id for s in senses]),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        deck_ok = item.source_deck_id and (
            await session.get(Deck, item.source_deck_id)
        )
        if owns is None and not (deck_ok and deck_ok.user_id == user.id):
            raise HTTPException(status_code=404, detail="Không tìm thấy lexical item")

    sense_ids = [s.id for s in senses]
    examples = (
        (
            await session.execute(
                select(ExampleSentence).where(ExampleSentence.sense_id.in_(sense_ids))
            )
        )
        .scalars()
        .all()
        if sense_ids
        else []
    )
    mnemonics = (
        (
            await session.execute(
                select(Mnemonic).where(Mnemonic.sense_id.in_(sense_ids))
            )
        )
        .scalars()
        .all()
        if sense_ids
        else []
    )

    return {
        "id": item.id,
        "surface_form": item.surface_form,
        "item_type": item.item_type,
        "ipa": item.ipa,
        "audio_url": audio_url_for(item.audio_path),
        "cefr_level": item.cefr_level,
        "academic_word_list_sublist": item.academic_word_list_sublist,
        "created_at": item.created_at,
        "senses": [
            {
                "id": s.id,
                "definition_en": s.definition_en,
                "definition_vi": s.definition_vi,
                "part_of_speech": s.part_of_speech,
                "register": s.register,
                "examples": [
                    {
                        "id": e.id,
                        "sentence": e.sentence,
                        "essay_type": e.essay_type,
                        "source": e.source,
                        "audio_url": audio_url_for(e.audio_path),
                    }
                    for e in examples
                    if e.sense_id == s.id
                ],
                "mnemonics": [
                    {
                        "id": m.id,
                        "mnemonic_text": m.mnemonic_text,
                        "mnemonic_type": m.mnemonic_type,
                    }
                    for m in mnemonics
                    if m.sense_id == s.id
                ],
            }
            for s in senses
        ],
    }
