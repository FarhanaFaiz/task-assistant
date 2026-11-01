import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.agent.service import generate_reply
from app.db.database import get_db
from app.db.models import Conversation, Message, User
from app.schemas.chat import ChatRequest, ChatResponse, ConversationResponse, MessageResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


def owned_conversation(conversation_id: int, user: User, db: Session) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/conversations", response_model=list[ConversationResponse])
def conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc())
        )
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
def messages(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_conversation(conversation_id, user, db)
    return list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
    )


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def chat(payload: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = (
        owned_conversation(payload.conversation_id, user, db)
        if payload.conversation_id is not None
        else Conversation(user_id=user.id, title=payload.message[:60])
    )
    if conversation.id is None:
        db.add(conversation)
        db.flush()
    user_message = Message(conversation_id=conversation.id, role="user", content=payload.message)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    try:
        reply = await asyncio.wait_for(
            generate_reply(payload.message, db, user, str(conversation.id)),
            timeout=30,
        )
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI assistant unavailable: {error}",
        ) from error
    assistant_message = Message(
        conversation_id=conversation.id, role="assistant", content=reply
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    return ChatResponse(conversation=conversation, message=assistant_message)
