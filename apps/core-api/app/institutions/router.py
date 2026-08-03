from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.models import User
from app.core.db import get_db
from app.core.ownership import get_owned
from app.institutions import service
from app.institutions.models import Institution, InstitutionStatus
from app.institutions.plaid_client import PlaidClient, get_plaid_client
from app.institutions.schemas import (
    InstitutionCreate,
    InstitutionResponse,
    LinkTokenResponse,
    SyncResponse,
)

router = APIRouter(prefix="/api/v1/institutions", tags=["institutions"])


@router.post("/link-token", response_model=LinkTokenResponse)
async def create_link_token(
    current_user: User = Depends(get_current_user),
    plaid_client: PlaidClient = Depends(get_plaid_client),
) -> LinkTokenResponse:
    link_token = await plaid_client.create_link_token(current_user.id)
    return LinkTokenResponse(link_token=link_token)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=InstitutionResponse)
async def link_institution(
    body: InstitutionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    plaid_client: PlaidClient = Depends(get_plaid_client),
) -> Institution:
    return await service.link_institution(
        db,
        plaid_client,
        current_user.id,
        body.public_token,
        body.institution_id,
        body.institution_name,
    )


@router.get("", response_model=list[InstitutionResponse])
async def list_institutions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Institution]:
    result = await db.scalars(
        select(Institution).where(
            Institution.user_id == current_user.id,
            Institution.status != InstitutionStatus.revoked,
        )
    )
    return list(result)


@router.post("/{institution_id}/sync", response_model=SyncResponse)
async def sync_institution(
    institution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    plaid_client: PlaidClient = Depends(get_plaid_client),
) -> SyncResponse:
    institution = await get_owned(db, Institution, institution_id, current_user.id)
    changed = await service.sync_institution(db, plaid_client, institution)
    return SyncResponse(transactions_changed=changed)


@router.delete("/{institution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_institution(
    institution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    plaid_client: PlaidClient = Depends(get_plaid_client),
) -> None:
    institution = await get_owned(db, Institution, institution_id, current_user.id)
    await service.unlink_institution(db, plaid_client, institution)
