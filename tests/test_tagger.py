import pytest
import numpy as np
from PIL import Image
from tagger import WDTagger, preprocess_image


def test_preprocess_image_output_shape():
    img = Image.new("RGB", (200, 300), "red")
    result = preprocess_image(img, target_size=448)
    assert result.shape == (1, 448, 448, 3)
    assert result.dtype == np.float32


def test_preprocess_image_rgba():
    img = Image.new("RGBA", (200, 200), (255, 0, 0, 128))
    result = preprocess_image(img, target_size=448)
    assert result.shape == (1, 448, 448, 3)


def test_preprocess_image_square_padding():
    # Wide image: 400x100 -> padded to 400x400 -> resized to 448x448
    img = Image.new("RGB", (400, 100), "blue")
    result = preprocess_image(img, target_size=448)
    assert result.shape == (1, 448, 448, 3)


def test_preprocess_bgr_conversion():
    # Create image with known R=255, G=0, B=0
    img = Image.new("RGB", (10, 10), (255, 0, 0))
    result = preprocess_image(img, target_size=10)
    # After BGR conversion: channel 0 should be B=0, channel 2 should be R=255
    assert result[0, 0, 0, 0] == 0.0    # B
    assert result[0, 0, 0, 2] == 255.0  # R


@pytest.fixture(scope="session")
def tagger():
    return WDTagger(models_dir="models")


def test_tagger_loads_model(tagger):
    assert tagger.session is not None
    assert len(tagger.tag_names) > 0
    assert len(tagger.rating_names) == 4


def test_tagger_predict_returns_tags_and_rating(tagger):
    img = Image.new("RGB", (512, 512), "red")
    tags, rating, rating_confidence = tagger.predict(img)
    assert isinstance(tags, list)
    assert isinstance(rating, str)
    assert rating in ("g", "s", "q", "e")
    assert 0.0 <= rating_confidence <= 1.0
