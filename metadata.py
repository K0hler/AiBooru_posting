import re
from dataclasses import dataclass, field

from PIL import Image

PARAMETER_REGEX = re.compile(r"\s*([\w ]+):\s*(\"(?:\\.|[^\"])*\"|[^,]*)(?:,|$)")


@dataclass
class AIMetadata:
    prompt: str = ""
    negative_prompt: str = ""
    sampler: str = ""
    seed: str = ""
    steps: str = ""
    cfg_scale: str = ""
    model_hash: str = ""
    parameters: dict = field(default_factory=dict)

    def is_present(self) -> bool:
        return bool(self.prompt or self.negative_prompt)


def parse_a1111_parameters(raw: str) -> AIMetadata:
    if not raw:
        return AIMetadata()

    lines = raw.strip().split("\n")

    # Find "Negative prompt:" line
    neg_idx = None
    for i, line in enumerate(lines):
        if line.startswith("Negative prompt:"):
            neg_idx = i
            break

    # Find last line with key-value params (starts with "Steps:")
    params_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("Steps:"):
            params_idx = i
            break

    # Extract prompt (everything before negative_prompt or params line)
    end = neg_idx if neg_idx is not None else params_idx
    prompt = "\n".join(lines[:end]).strip() if end is not None else raw.strip()

    # Extract negative prompt
    negative_prompt = ""
    if neg_idx is not None:
        neg_end = params_idx if params_idx is not None else len(lines)
        neg_lines = lines[neg_idx:neg_end]
        neg_lines[0] = neg_lines[0].replace("Negative prompt:", "", 1).strip()
        negative_prompt = "\n".join(neg_lines).strip()

    # Parse key-value parameters from last line
    params = {}
    sampler = seed = steps = cfg_scale = model_hash = ""
    if params_idx is not None:
        params_line = lines[params_idx]
        for match in PARAMETER_REGEX.finditer(params_line):
            key = match.group(1).strip()
            val = match.group(2).strip().strip('"')
            params[key] = val

        sampler = params.pop("Sampler", "")
        seed = params.pop("Seed", "")
        steps = params.pop("Steps", "")
        cfg_scale = params.pop("CFG scale", "")
        model_hash = params.pop("Model hash", "")

    return AIMetadata(
        prompt=prompt,
        negative_prompt=negative_prompt,
        sampler=sampler,
        seed=seed,
        steps=steps,
        cfg_scale=cfg_scale,
        model_hash=model_hash,
        parameters=params,
    )


def extract_a1111_metadata(file_path: str) -> AIMetadata:
    if not file_path.lower().endswith(".png"):
        return AIMetadata()
    try:
        img = Image.open(file_path)
        raw = img.info.get("parameters", "")
        return parse_a1111_parameters(raw)
    except Exception:
        return AIMetadata()
