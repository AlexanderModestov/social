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


def test_config_uses_duration_setting():
    svc = VeoService()
    cfg = svc._config()
    assert cfg.duration_seconds == 8
    assert cfg.aspect_ratio == "9:16"


def test_normalize_cmd_forces_1080x1920(tmp_path):
    svc = VeoService()
    cmd = svc._normalize_cmd("in.jpg", "out.jpg")
    assert cmd[0] == "ffmpeg"
    assert "in.jpg" in cmd and "out.jpg" in cmd
    vf = cmd[cmd.index("-vf") + 1]
    assert "1080:1920" in vf
    assert "crop=1080:1920" in vf


def test_build_concat_file_writes_one_line_per_clip(tmp_path):
    svc = VeoService()
    clips = [str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4")]
    list_path = svc._build_concat_file(clips, str(tmp_path))
    content = open(list_path).read().splitlines()
    assert content == [f"file '{clips[0]}'", f"file '{clips[1]}'"]
