"""Message handlers for async classification workflow."""
import logging
from infrastructure.mq.inprocess_queue import inprocess_mq

logger = logging.getLogger(__name__)

_classification_handler = None
_app = None


def set_classification_handler(handler):
    global _classification_handler
    _classification_handler = handler
    logger.info("Classification handler registered")


def set_app(app):
    """Store Flask app reference for pushing context in background threads."""
    global _app
    _app = app


def handle_email_input(message):
    """Process new email from queue - trigger classification."""
    logger.info(f"Processing email from queue: {message.get('data', {}).get('email_id')}")
    if _classification_handler:
        data = message.get('data', {})
        try:
            if _app:
                with _app.app_context():
                    result = _classification_handler(
                        email_id=data.get('email_id'),
                        sender=data.get('sender', ''),
                        subject=data.get('subject', ''),
                        content=data.get('content', '')
                    )
            else:
                result = _classification_handler(
                    email_id=data.get('email_id'),
                    sender=data.get('sender', ''),
                    subject=data.get('subject', ''),
                    content=data.get('content', '')
                )
            logger.info(f"Async classification complete: {result.get('final_category') if result else 'failed'}")
        except Exception as e:
            logger.error(f"Async classification error: {e}")


def handle_classification_result(message):
    """Log classification results from queue."""
    data = message.get('data', {})
    logger.info(f"Classification result logged: email_id={data.get('email_id')}, "
                f"category={data.get('result', {}).get('final_category')}")


def register_all_handlers():
    """Register all message handlers."""
    inprocess_mq.subscribe('email_input', handle_email_input)
    inprocess_mq.subscribe('classification_result', handle_classification_result)
    logger.info("All MQ handlers registered")
