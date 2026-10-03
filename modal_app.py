"""Modal app for S5 frozen embeddings (and optional S4 / S7 fan-out). Owner: P3.

    modal run modal_app.py --batch Batch_1          # embed one batch, log time and cost
    modal deploy modal_app.py                       # optional endpoint for the Streamlit screen

Guardrails: max_containers capped, timeouts set, weights cached in a Volume, no secrets in code.
See docs/FRAMEWORK.md Sections 8 and 12.8. Not implemented yet.
"""
import modal

app = modal.App("aixscience-qc")
weights = modal.Volume.from_name("aixscience-weights", create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch", "torchvision", "numpy", "tifffile", "imagecodecs", "pyarrow", "pandas")
)


@app.function(image=image, gpu="L4", volumes={"/weights": weights}, timeout=20 * 60, max_containers=20)
def embed_tiles(tile_paths: list[str]) -> dict:
    raise NotImplementedError("S5: load DINOv2 ViT-S/14 once per container in @modal.enter, embed tiles, return vectors")


@app.local_entrypoint()
def main(batch: str = "Batch_1"):
    print(f"would embed {batch}; implement features.py + embed_tiles first")
