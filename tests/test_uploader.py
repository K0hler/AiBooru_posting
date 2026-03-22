import pytest
from unittest.mock import patch, MagicMock, mock_open
from uploader import AIBooruUploader


@pytest.fixture
def uploader():
    return AIBooruUploader(login="testuser", api_key="testkey")


def test_startup_check_success(uploader):
    with patch("uploader.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        assert uploader.check_connection() is True


def test_startup_check_auth_failure(uploader):
    with patch("uploader.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=401)
        assert uploader.check_connection() is False


def test_upload_file_returns_id(uploader):
    with patch("uploader.requests.post") as mock_post, \
         patch("builtins.open", mock_open(read_data=b"fake image data")):
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"id": 42},
        )
        upload_id = uploader.upload_file("test.png")
        assert upload_id == 42


def test_create_post_success(uploader):
    with patch("uploader.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"id": 100})
        post_id = uploader.create_post(
            media_asset_id=99,
            tags="1girl blue_hair",
            rating="s",
        )
        assert post_id == 100


def test_wait_for_processing_success(uploader):
    with patch("uploader.requests.get") as mock_get, \
         patch("uploader.time.sleep"):
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {
                "status": "processing",
                "upload_media_assets": [{"id": 99}],
            }),
            MagicMock(status_code=200, json=lambda: {
                "status": "completed",
                "upload_media_assets": [{"id": 99}],
            }),
        ]
        media_id = uploader.wait_for_processing(42)
        assert media_id == 99


def test_upload_file_rate_limited_retries(uploader):
    with patch("uploader.requests.post") as mock_post, \
         patch("builtins.open", mock_open(read_data=b"fake image data")), \
         patch("uploader.time.sleep"):
        mock_post.side_effect = [
            MagicMock(status_code=429, headers={}),
            MagicMock(
                status_code=201,
                json=lambda: {"id": 42},
            ),
        ]
        upload_id = uploader.upload_file("test.png")
        assert upload_id == 42
