from PIL import Image, PngImagePlugin
from metadata import extract_a1111_metadata


def _create_png_with_metadata(path, params_text: str):
    img = Image.new("RGB", (100, 100), "red")
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", params_text)
    img.save(str(path), pnginfo=info)


def test_extract_full_metadata(tmp_path):
    params = (
        "1girl, blue hair, school uniform\n"
        "Negative prompt: bad anatomy, worst quality\n"
        "Steps: 20, Sampler: Euler a, CFG scale: 7, Seed: 12345, "
        "Size: 512x768, Model: animagineXL"
    )
    path = tmp_path / "test.png"
    _create_png_with_metadata(path, params)
    result = extract_a1111_metadata(str(path))
    assert "1girl, blue hair, school uniform" in result
    assert "animagineXL" in result
    assert "12345" in result


def test_extract_no_metadata_returns_empty(tmp_path):
    path = tmp_path / "test.png"
    Image.new("RGB", (100, 100)).save(str(path))
    result = extract_a1111_metadata(str(path))
    assert result == ""


def test_extract_from_jpg_returns_empty(tmp_path):
    path = tmp_path / "test.jpg"
    Image.new("RGB", (100, 100)).save(str(path))
    result = extract_a1111_metadata(str(path))
    assert result == ""
