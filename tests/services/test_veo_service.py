import pytest

from bot.services.veo_service import VeoService, _get_client


class _FakeVideo:
    def __init__(self, video_bytes):
        self.video_bytes = video_bytes


def test_write_clip_writes_bytes():
    svc = VeoService()
    path = svc._write_clip(_FakeVideo(b"hello"))
    with open(path, "rb") as f:
        assert f.read() == b"hello"


def test_write_clip_raises_without_bytes():
    svc = VeoService()
    with pytest.raises(RuntimeError):
        svc._write_clip(_FakeVideo(None))


def test_import_does_not_require_credentials():
    # Construction must not build the Vertex client or touch the network.
    svc = VeoService()
    assert svc is not None


def test_client_is_lazy_and_cached():
    assert hasattr(_get_client, "cache_clear")


def test_build_concat_file_writes_one_line_per_clip(tmp_path):
    svc = VeoService()
    clips = [str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4")]
    list_path = svc._build_concat_file(clips, str(tmp_path))
    content = open(list_path).read().splitlines()
    assert content == [f"file '{clips[0]}'", f"file '{clips[1]}'"]
