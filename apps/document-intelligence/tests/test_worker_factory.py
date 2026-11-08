"""The production worker entry point uses the page analyzer and chat."""

from unittest.mock import Mock, patch

from document_intelligence.worker import main


def test_main_uses_page_analyzer_and_chat() -> None:
    analyzer = Mock()
    repository = Mock()
    queue = Mock()
    with (
        patch("document_intelligence.worker.Settings") as settings_type,
        patch("document_intelligence.worker.build_repository", return_value=repository),
        patch("document_intelligence.worker.build_queue", return_value=queue),
        patch("document_intelligence.worker.build_blobs", return_value=Mock()),
        patch("document_intelligence.worker.build_page_analyzer", return_value=analyzer) as factory,
        patch("document_intelligence.worker.build_page_chat", return_value=Mock()) as chat_factory,
        patch("document_intelligence.worker.Worker") as worker_type,
    ):
        settings = Mock()
        settings.repository_backend = "postgres"
        settings.max_job_attempts = 3
        settings.max_upload_bytes = 10_000_000
        settings.page_concurrency = 3
        settings.page_text_max_chars = 24_000
        settings_type.return_value = settings
        main()

    factory.assert_called_once_with(settings)
    chat_factory.assert_called_once_with(settings)
    worker_type.return_value.run_forever.assert_called_once_with()
    queue.close.assert_called_once_with()
    repository.close.assert_called_once_with()
