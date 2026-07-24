"""Helpers that keep users.tag / users.current_state / last_active_at in sync with FSM.

The TZ requires the in-memory FSM state to also be persisted in DB so that
bot restarts don't lose context. Every tag transition is also recorded in
`user_tag_history` for accurate drop-off analytics.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update

from database.models import User, UserTagHistory


def utcnow() -> datetime:
    """Timezone-aware UTC now (replaces deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc)


async def update_user_state(session, telegram_id: int, state_name: str | None) -> None:
    """Persist the current FSM state name to users.current_state."""
    await session.execute(
        update(User).where(User.telegram_id == telegram_id).values(
            current_state=state_name,
            last_active_at=utcnow(),
        )
    )
    await session.commit()


async def update_user_tag(session, telegram_id: int, tag: str) -> None:
    """Update users.tag and append to user_tag_history.

    Old tag is preserved for analytics even if user later re-enters the flow.
    """
    row = (
        await session.execute(
            select(User.tag).where(User.telegram_id == telegram_id)
        )
    ).scalar_one_or_none()
    old_tag = row if row else "start_bosdi"

    await session.execute(
        update(User).where(User.telegram_id == telegram_id).values(
            tag=tag,
            last_active_at=utcnow(),
        )
    )
    # Record history (only if changed)
    if old_tag != tag:
        user_id_row = (
            await session.execute(
                select(User.id).where(User.telegram_id == telegram_id)
            )
        ).scalar_one_or_none()
        if user_id_row:
            session.add(
                UserTagHistory(
                    user_id=user_id_row,
                    old_tag=old_tag,
                    new_tag=tag,
                )
            )
    await session.commit()


async def touch_user(session, telegram_id: int) -> None:
    """Just bump last_active_at (e.g. on any incoming message)."""
    await session.execute(
        update(User).where(User.telegram_id == telegram_id).values(
            last_active_at=utcnow(),
        )
    )
    await session.commit()


async def reset_reminder(session, telegram_id: int) -> None:
    """Reset reminder_sent flag whenever the user resumes activity."""
    await session.execute(
        update(User).where(User.telegram_id == telegram_id).values(
            reminder_sent=0,
            last_active_at=utcnow(),
        )
    )
    await session.commit()
