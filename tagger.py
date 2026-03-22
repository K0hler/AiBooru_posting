import csv
from pathlib import Path

import numpy as np
import onnxruntime as rt
from huggingface_hub import hf_hub_download
from PIL import Image

MODEL_REPO = "SmilingWolf/wd-swinv2-tagger-v3"
GENERAL_THRESHOLD = 0.35
CHARACTER_THRESHOLD = 0.85
RATING_MAP = {"general": "g", "sensitive": "s", "questionable": "q", "explicit": "e"}


def preprocess_image(image: Image.Image, target_size: int = 448) -> np.ndarray:
    # RGBA -> composite on white -> RGB
    if image.mode == "RGBA":
        canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
        canvas.alpha_composite(image)
        image = canvas.convert("RGB")
    elif image.mode != "RGB":
        image = image.convert("RGB")

    # Pad to square with white background
    w, h = image.size
    max_dim = max(w, h)
    padded = Image.new("RGB", (max_dim, max_dim), (255, 255, 255))
    padded.paste(image, ((max_dim - w) // 2, (max_dim - h) // 2))

    # Resize to target
    padded = padded.resize((target_size, target_size), Image.LANCZOS)

    # To numpy, RGB -> BGR, float32 (no normalization)
    arr = np.array(padded, dtype=np.float32)
    arr = arr[:, :, ::-1]  # RGB -> BGR
    return np.expand_dims(arr, axis=0)


class WDTagger:
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)
        self._download_model()
        self._load_labels()
        self.session = rt.InferenceSession(
            str(self.models_dir / "model.onnx"),
            providers=["CPUExecutionProvider"],
        )
        input_shape = self.session.get_inputs()[0].shape
        self.target_size = input_shape[1]  # typically 448

    def _download_model(self):
        for filename in ("model.onnx", "selected_tags.csv"):
            target = self.models_dir / filename
            if not target.exists():
                print(f"Скачивание {filename}...")
                hf_hub_download(
                    repo_id=MODEL_REPO,
                    filename=filename,
                    local_dir=str(self.models_dir),
                )

    def _load_labels(self):
        self.tag_names = []
        self.tag_categories = []
        self.rating_names = []
        self.rating_indices = []
        self.general_indices = []
        self.character_indices = []

        csv_path = self.models_dir / "selected_tags.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                name = row["name"]
                category = int(row["category"])
                self.tag_names.append(name)
                self.tag_categories.append(category)
                if category == 9:
                    self.rating_names.append(name)
                    self.rating_indices.append(i)
                elif category == 0:
                    self.general_indices.append(i)
                elif category == 4:
                    self.character_indices.append(i)

    def predict(self, image: Image.Image) -> tuple[list[str], str, float]:
        input_data = preprocess_image(image, self.target_size)
        input_name = self.session.get_inputs()[0].name
        output = self.session.run(None, {input_name: input_data})[0][0]

        # Rating: pick highest confidence
        rating_scores = {self.tag_names[i]: float(output[i]) for i in self.rating_indices}
        best_rating_name = max(rating_scores, key=rating_scores.get)
        rating = RATING_MAP.get(best_rating_name, "g")
        rating_confidence = rating_scores[best_rating_name]

        # General tags
        tags = []
        for i in self.general_indices:
            if output[i] > GENERAL_THRESHOLD:
                tag = self.tag_names[i].replace(" ", "_")
                tags.append(tag)

        # Character tags (higher threshold)
        for i in self.character_indices:
            if output[i] > CHARACTER_THRESHOLD:
                tag = self.tag_names[i].replace(" ", "_")
                tags.append(tag)

        return tags, rating, rating_confidence
