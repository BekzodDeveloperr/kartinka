"""Broadcast: send a message to all users matching a tag (with blocked-user tracking)."""
from __future__ import annotations

import asyncio
import logging

from aiogram import F, Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from database.db import async_session
from database.models import AdminUser, BroadcastLog, User
from keyboards.admin_kb import admin_back_kb, admin_broadcast_target_kb
from states.order_states import AdminFlow
from utils.security import IsAdminFilter, HasPermissionFilter

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())

log = logging.getLogger(__name__)

BATCH_SIZE = 10
BATCH_DELAY = 1.0


@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast_start(callback: CallbackQuery):
    perms = await _get_perms(callback.from_user.id)
    if "broadcast" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    await callback.message.edit_text(
        "📢 <b>Xabar yuborish</b>\n\n"
        "Qaysi foydalanuvchilar guruhiga yuboramiz? (status / tag bo'yicha)",
        reply_markup=admin_broadcast_target_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bc:target:"))
async def cb_broadcast_pick_target(callback: CallbackQuery, state: FSMContext):
    perms = await _get_perms(callback.from_user.id)
    if "broadcast" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, _, tag = callback.data.split(":")
    except ValueError:
        await callback.answer()
        return
    await state.set_state(AdminFlow.waiting_broadcast_text)
    await state.update_data(broadcast_target=tag)
    await callback.message.edit_text(
        f"✏️ Endi yubormoqchi bo'lgan matningizni yozing.\n\n"
        f"Maqsad: <b>{tag}</b>\n\n"
        "(Matn barcha tanlangan foydalanuvchilarga yuboriladi. Bekor qilish uchun /admin)",
        reply_markup=admin_back_kb("admin:broadcast"),
    )
    await callback.answer()


@router.message(AdminFlow.waiting_broadcast_text)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    perms = await _get_perms(message.from_user.id)
    if "broadcast" not in perms:
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Matn bo'sh bo'lishi mumkin emas. Qaytadan urining.")
        return
    data = await state.get_data()
    target = data.get("broadcast_target", "all")
    await state.clear()

    async with async_session() as session:
        q = select(User.telegram_id, User.username, User.id)
        if target != "all":
            q = q.where(User.tag == target)
        rows = (await session.execute(q)).all()

    sent = 0
    failed = 0
    blocked_ids: list[int] = []
    blocked_usernames: list[str] = []
    total = len(rows)

    # Send in batches
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        coros = [_safe_send(bot, tg_id, text) for tg_id, _, _ in batch]
        results = await asyncio.gather(*coros, return_exceptions=True)
        for (tg_id, uname, _), r in zip(batch, results):
            if r is True:
                sent += 1
            else:
                failed += 1
                if r == "blocked":
                    blocked_ids.append(tg_id)
                    if uname:
                        blocked_usernames.append(f"@{uname}")
                    else:
                        blocked_usernames.append(str(tg_id))
        if i + BATCH_SIZE < total:
            await asyncio.sleep(BATCH_DELAY)

    async with async_session() as session:
        session.add(
            BroadcastLog(
                admin_id=message.from_user.id,
                target_tag=target,
                message=text,
                sent_count=sent,
                failed_count=failed,
                blocked_user_ids=",".join(str(x) for x in blocked_ids),
            )
        )
        await session.commit()

    blocked_display = ", ".join(blocked_usernames) if blocked_usernames else "(yo'q)"
    await message.answer(
        f"✅ Xabar yuborildi.\n\n"
        f"🎯 Maqsad: {target}\n"
        f"👥 Jami: {total}\n"
        f"✅ Yuborildi: {sent}\n"
        f"❌ Yetkazilmadi: {failed}\n"
        f"🚫 Bloklaganlar ({len(blocked_ids)}): {blocked_display}",
        reply_markup=admin_back_kb("admin:panel"),
    )


async def _safe_send(bot: Bot, tg_id: int, text: str):
    try:
        await bot.send_message(tg_id, text)
        return True
    except Exception as e:
        msg = str(e).lower()
        if "forbidden" in msg or "blocked" in msg or "user is deactivated" in msg:
            return "blocked"
        return False


async def _get_perms(telegram_id: int) -> set[str]:
    from utils.security import get_admin_role_async, _role_permissions
    role = await get_admin_role_async(telegram_id)
    return _role_permissions().get(role, set()) if role else set()
