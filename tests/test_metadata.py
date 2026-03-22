from PIL import Image, PngImagePlugin
from metadata import extract_a1111_metadata, parse_a1111_parameters


def _create_png_with_metadata(path, params_text: str):
    img = Image.new("RGB", (100, 100), "red")
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", params_text)
    img.save(str(path), pnginfo=info)


SAMPLE_PARAMS = (
    "1girl, blue hair, school uniform\n"
    "Negative prompt: bad anatomy, worst quality\n"
    "Steps: 20, Sampler: Euler a, CFG scale: 7, Seed: 12345, "
    "Size: 512x768, Model hash: abcdef1234, Model: animagineXL"
)


def test_parse_a1111_parameters():
    meta = parse_a1111_parameters(SAMPLE_PARAMS)
    assert meta.prompt == "1girl, blue hair, school uniform"
    assert meta.negative_prompt == "bad anatomy, worst quality"
    assert meta.steps == "20"
    assert meta.sampler == "Euler a"
    assert meta.cfg_scale == "7"
    assert meta.seed == "12345"
    assert meta.model_hash == "abcdef1234"
    assert meta.parameters["Model"] == "animagineXL"
    assert meta.is_present()


def test_parse_empty_returns_empty():
    meta = parse_a1111_parameters("")
    assert not meta.is_present()
    assert meta.prompt == ""
    assert meta.negative_prompt == ""


def test_parse_prompt_only():
    meta = parse_a1111_parameters("1girl, solo, standing")
    assert meta.prompt == "1girl, solo, standing"
    assert meta.negative_prompt == ""
    assert meta.is_present()


def test_extract_from_png(tmp_path):
    path = tmp_path / "test.png"
    _create_png_with_metadata(path, SAMPLE_PARAMS)
    meta = extract_a1111_metadata(str(path))
    assert meta.is_present()
    assert meta.prompt == "1girl, blue hair, school uniform"
    assert meta.seed == "12345"


def test_extract_no_metadata_returns_empty(tmp_path):
    path = tmp_path / "test.png"
    Image.new("RGB", (100, 100)).save(str(path))
    meta = extract_a1111_metadata(str(path))
    assert not meta.is_present()


def test_extract_from_jpg_returns_empty(tmp_path):
    path = tmp_path / "test.jpg"
    Image.new("RGB", (100, 100)).save(str(path))
    meta = extract_a1111_metadata(str(path))
    assert not meta.is_present()
