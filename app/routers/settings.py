from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Setting
from app.schemas.setting import SettingResponse, SettingsBatchUpdate, SettingUpdate
from app.services.auth import get_current_user, require_admin, UserInfo

router = APIRouter(prefix="/settings", tags=["settings"])

REQUIRED_KEYS = [
    "payment_card_number",
    "payment_card_owner",
    "payment_bank",
    "telegram_bot_token",
    "telegram_group_id",
    "telegram_group_link",
    "instagram_page_id",
    "instagram_access_token",
    "timezone",
    "working_hours_start",
    "working_hours_end",
    "is_24_7",
    "offline_message",
]


@router.get("", response_model=list[SettingResponse])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    result = await db.execute(select(Setting).order_by(Setting.key))
    return result.scalars().all()


@router.put("", response_model=list[SettingResponse])
async def update_settings(
    body: SettingsBatchUpdate,
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    result = await db.execute(select(Setting))
    existing = {s.key: s for s in result.scalars().all()}

    for key, value in body.settings.items():
        if key in existing:
            existing[key].value = value
        else:
            db.add(Setting(key=key, value=value))

    await db.commit()

    result = await db.execute(select(Setting).order_by(Setting.key))
    return result.scalars().all()


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    body: SettingUpdate,
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = body.value
    else:
        setting = Setting(key=key, value=body.value)
        db.add(setting)
    await db.commit()
    await db.refresh(setting)
    return setting


@router.post("/test-telegram")
async def test_telegram(
    _: UserInfo = Depends(require_admin),
):
    from app.services.telegram import send_admin_alert
    from datetime import datetime

    try:
        await send_admin_alert(
            f"Test message from admin panel at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return {"status": "sent"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Telegram send failed: {exc}")
