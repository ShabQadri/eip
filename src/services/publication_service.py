import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from src.models.published_post import PublishedPost

logger = logging.getLogger("eip.publication_service")

class PublicationService:
    """
    Helper service to check and log publication states for canonical events.
    """
    def is_published(
        self,
        session: Session,
        event_id: str,
        platform: str,
        post_type: str
    ) -> bool:
        """
        Checks if an event is published to a platform for a specific post type.
        """
        record = session.query(PublishedPost).filter_by(
            event_id=event_id,
            platform=platform.upper(),
            post_type=post_type.upper()
        ).first()
        return record is not None

    def mark_published(
        self,
        session: Session,
        event_id: str,
        platform: str,
        post_type: str,
        external_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        message_id: Optional[str] = None
    ) -> PublishedPost:
        """
        Logs a publication record in the published_posts table.
        """
        # Backward compatibility for message_id
        actual_external_id = external_id
        if actual_external_id is None and message_id is not None:
            actual_external_id = message_id

        actual_metadata = metadata or {}
        if platform.upper() == "TELEGRAM" and actual_external_id and "message_id" not in actual_metadata:
            actual_metadata["message_id"] = actual_external_id

        post = PublishedPost(
            event_id=event_id,
            platform=platform.upper(),
            post_type=post_type.upper(),
            external_id=actual_external_id,
            metadata_json=actual_metadata
        )
        session.add(post)
        session.flush()
        return post

    def get_publication(
        self,
        session: Session,
        event_id: str,
        platform: str,
        post_type: str
    ) -> Optional[PublishedPost]:
        """
        Retrieves a specific publication record if it exists.
        """
        return session.query(PublishedPost).filter_by(
            event_id=event_id,
            platform=platform.upper(),
            post_type=post_type.upper()
        ).first()

    def get_publications(
        self,
        session: Session,
        event_id: str
    ) -> List[PublishedPost]:
        """
        Retrieves all logged publications for a given event.
        """
        return session.query(PublishedPost).filter_by(event_id=event_id).all()
