import uuid
from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from backend.app.next_of_kin.models import NextOfKin
from backend.app.next_of_kin.schema import NextOfKinCreateSchema, NextOfKinReadSchema, NextOfKinUpdateSchema
from backend.app.core.logging import get_logger

logger = get_logger()


async def get_next_of_kin_count(user_id: uuid.UUID, session: AsyncSession) -> int:
    try:
        statement = select(NextOfKin).where(NextOfKin.user_id == user_id)
        result = await session.exec(statement)
        next_of_kins = result.all()
        return len(next_of_kins)
    except Exception as e:
        logger.error(f"Error fetching next of kin count for user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while fetching the next of kin count.",
            },
        )


async def get_primary_next_of_kin(
    user_id: uuid.UUID, session: AsyncSession
) -> NextOfKin | None:
    try:
        statement = select(NextOfKin).where(
            NextOfKin.user_id == user_id, NextOfKin.is_primary_contact == True
        )
        result = await session.exec(statement)
        return result.first()
    except Exception as e:
        logger.error(f"Error fetching primary next of kin for user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while fetching the primary next of kin.",
            },
        )


async def validate_next_of_kin_creation(
    user_id: uuid.UUID,
    is_primary_contact: bool,
    session: AsyncSession,
) -> None:
    current_count = await get_next_of_kin_count(user_id, session)
    if current_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": "Maximum of 3 next of kin allowed.",
            },
        )

    if is_primary_contact:
        existing_primary = await get_primary_next_of_kin(user_id, session)
        if existing_primary:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "A primary next of kin already exists.",
                },
            )


async def create_next_of_kin(
    user_id: uuid.UUID,
    next_of_kin_data: NextOfKinCreateSchema,
    session: AsyncSession,
) -> NextOfKinReadSchema:
    try:
        await validate_next_of_kin_creation(
            user_id,
            next_of_kin_data.is_primary_contact,
            session,
        )
        current_count = await get_next_of_kin_count(user_id, session)

        if current_count == 0:
            next_of_kin_data.is_primary_contact = True

        next_of_kin = NextOfKin(
            **next_of_kin_data.model_dump(),
            user_id=user_id,
        )

        session.add(next_of_kin)
        await session.commit()
        await session.refresh(next_of_kin)

        logger.info(f"Created new next of kin for user_id {user_id}")
        return NextOfKinReadSchema.model_validate(next_of_kin)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating next of kin for user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while creating the next of kin.",
            },
        )


async def get_next_of_kins_by_user(
    user_id: uuid.UUID,
    session: AsyncSession,
) -> list[NextOfKin]:
    try:
        statement = select(NextOfKin).where(NextOfKin.user_id == user_id)
        result = await session.exec(statement)
        return list(result.all())
    except Exception as e:
        logger.error(f"Error fetching next of kins for user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while fetching the next of kins.",
            },
        )


async def get_user_next_of_kin(
    user_id: uuid.UUID,
    next_of_kin_id: uuid.UUID,
    session: AsyncSession,
) -> NextOfKin:
    try:
        statement = select(NextOfKin).where(
            NextOfKin.user_id == user_id, NextOfKin.id == next_of_kin_id
        )
        result = await session.exec(statement)
        next_of_kin = result.first()
        if not next_of_kin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Next of kin not found.",
                },
            )
        return next_of_kin
    except Exception as e:
        logger.error(
            f"Error fetching next of kin {next_of_kin_id} for user_id {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while fetching the next of kin.",
            },
        )

async def update_next_of_kin(
    user_id: uuid.UUID,
    next_of_kin_id: uuid.UUID,
    next_of_kin_data: NextOfKinUpdateSchema,
    session: AsyncSession,
) -> NextOfKin:
    try:
        next_of_kin = await get_user_next_of_kin(user_id, next_of_kin_id, session)

        if next_of_kin_data.is_primary_contact is not None:
            if next_of_kin_data.is_primary_contact:
                existing_primary = await get_primary_next_of_kin(user_id, session)
                if existing_primary and existing_primary.id != next_of_kin_id:
                    existing_primary.is_primary_contact = False
                    session.add(existing_primary)
            else:
                if next_of_kin.is_primary_contact:
                    total_count = await get_next_of_kin_count(user_id, session)
                    if total_count > 1:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail={
                                "status": "error",
                                "message": "Cannot remove primary status. At least one next of kin must be primary. Please set another next of kin as primary first.",
                            },
                        )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail={
                                "status": "error",
                                "message": "At least one next of kin must be primary.",
                            },
                        )

        for key, value in next_of_kin_data.model_dump(exclude_unset=True).items():
            setattr(next_of_kin, key, value)

        session.add(next_of_kin)
        await session.commit()
        await session.refresh(next_of_kin)
        logger.info(f"Updated next of kin {next_of_kin_id} for user_id {user_id}")
        return next_of_kin
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Error updating next of kin {next_of_kin_id} for user_id {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while updating the next of kin.",
            },
        )

async def delete_next_of_kin(
    user_id: uuid.UUID,
    next_of_kin_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, str]:
    try:
        total_count = await get_next_of_kin_count(user_id, session)
        if total_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "At least one next of kin must be retained.",
                },
            )
        primary_next_of_kin = await get_primary_next_of_kin(user_id, session)
        if primary_next_of_kin and primary_next_of_kin.id == next_of_kin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Cannot delete primary next of kin. Please set another next of kin as primary first.",
                },
            )
        next_of_kin = await get_user_next_of_kin(user_id, next_of_kin_id, session)
        await session.delete(next_of_kin)
        await session.commit()
        logger.info(f"Deleted next of kin {next_of_kin_id} for user_id {user_id}")
        return {
            "status": "success",
            "message": "Next of kin deleted successfully.",
        }
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Error deleting next of kin {next_of_kin_id} for user_id {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An error occurred while deleting the next of kin.",
            },
        )