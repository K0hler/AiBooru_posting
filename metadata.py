from PIL import Image


def extract_a1111_metadata(file_path: str) -> str:
    if not file_path.lower().endswith(".png"):
        return ""
    try:
        img = Image.open(file_path)
        return img.info.get("parameters", "")
    except Exception:
        return ""
