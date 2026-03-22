from PIL import Image


MAX_SOURCE_LENGTH = 1200


def extract_a1111_metadata(file_path: str) -> str:
    if not file_path.lower().endswith(".png"):
        return ""
    try:
        img = Image.open(file_path)
        params = img.info.get("parameters", "")
        if len(params) > MAX_SOURCE_LENGTH:
            params = params[:MAX_SOURCE_LENGTH - 3] + "..."
        return params
    except Exception:
        return ""
