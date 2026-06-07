from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.models.subscription import Subscription
from uuid import UUID

import stripe
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.subscription import Subscription
from app.models.quota import QuotaUsage
from app.models.enums import SubscriptionStatus

logger = structlog.get_logger()

# Tier → Stripe Price ID mapping
TIER_PRICE_MAP: dict[str, str] = {
    "spark": settings.STRIPE_PRICE_SPARK_MONTHLY,
    "creator": settings.STRIPE_PRICE_CREATOR_MONTHLY,
    "artist": settings.STRIPE_PRICE_ARTIST_MONTHLY,
    "studio_pro": settings.STRIPE_PRICE_STUDIO_PRO_MONTHLY,
}

async def get_current_tier(user_id: UUID, db: AsyncSession) -> str:
    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(user_id)})
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.status == "active")
        .order_by(Subscription.current_period_end.desc())
    )
    sub = result.scalar_one_or_none()
    return sub.tier if sub else "free"
