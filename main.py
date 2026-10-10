"""
The AI Thumbnail A/B Tester & Hook Generator
Uses Qwen-Image-2.1-Turbo (Diffusers) and local Ollama to generate 4 high-CTR thumbnail variations
from an input base video frame and user tagline.
"""

import os
import sys
import argparse
import requests
import torch
from PIL import Image

try:
    from diffusers import QwenImage21Pipeline
except ImportError:
    QwenImage21Pipeline = None

MODEL_DIR = os.path.join("models", "Qwen-Image-2.1-Turbo")
INPUT_FRAME = os.path.join("inputs", "base_frame.jpg")
OUTPUT_GRID = os.path.join("outputs", "thumbnail_ab_grid.jpg")
OLLAMA_API = "http://127.0.0.1:11434/api/generate"

def query_ollama_hooks(tagline, model_name="qwen2.5:latest"):
    """Queries local Ollama model to generate 4 punchy viral thumbnail hook variations."""
    print(f"\n[Ollama Engine] Requesting 4 viral thumbnail hooks for tagline:")
    print(f"  Tagline: \"{tagline}\"")
    
    system_prompt = (
        "You are a top YouTube CTR optimization expert. Given a video tagline, produce exactly 4 viral thumbnail text hooks "
        "(3 to 5 words each, all uppercase, high curiosity/shock value). "
        "Format your answer as exactly 4 lines, without numbering or extra commentary."
    )
    user_prompt = f"Tagline: {tagline}\nGenerate 4 thumbnail hooks:"
    
    response = requests.post(
        OLLAMA_API,
        json={
            "model": model_name,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": False,
            "options": {"temperature": 0.85, "top_p": 0.9}
        },
        timeout=15
    )
    response.raise_for_status()
    raw_output = response.json().get("response", "").strip()
    
    lines = [
        line.strip().lstrip("1234.- ").strip('"').strip("'").upper()
        for line in raw_output.split("\n")
        if line.strip()
    ][:4]
    
    if len(lines) < 4:
        raise ValueError(f"Ollama returned fewer than 4 hooks: {raw_output}")
    
    print("[Ollama Engine] Successfully generated hooks:")
    for i, h in enumerate(lines, 1):
        print(f"  Variant {i}: {h}")
    return lines

def load_pipeline():
    """Loads Qwen-Image-2.1-Turbo pipeline directly via diffusers."""
    model_source = MODEL_DIR if os.path.exists(MODEL_DIR) else "Qwen/Qwen-Image-2.1-Turbo"
    print(f"[Qwen Engine] Loading pipeline from: {model_source}")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    
    pipe = QwenImage21Pipeline.from_pretrained(
        model_source,
        dtype=dtype,
    ).to(device)
    return pipe

def stitch_ab_grid(variations):
    """Stitches 4 generated thumbnail variations into a 2x2 comparison grid."""
    w, h = 1280, 720
    grid = Image.new("RGB", (w * 2, h * 2), (10, 12, 18))
    
    positions = [
        (0, 0),        # Top-Left (Variant 1)
        (w, 0),        # Top-Right (Variant 2)
        (0, h),        # Bottom-Left (Variant 3)
        (w, h)         # Bottom-Right (Variant 4)
    ]
    
    for img, pos in zip(variations, positions):
        resized = img.resize((w, h), Image.Resampling.LANCZOS)
        grid.paste(resized, pos)
        
    os.makedirs(os.path.dirname(OUTPUT_GRID), exist_ok=True)
    grid.save(OUTPUT_GRID, "JPEG", quality=95)
    print(f"\n[Result] 4-way A/B thumbnail grid saved to: {OUTPUT_GRID}")

def main():
    parser = argparse.ArgumentParser(description="AI Thumbnail A/B Tester & Hook Generator")
    parser.add_argument(
        "--tagline",
        type=str,
        required=True,
        help="An 8-9 word single line tagline describing your video topic"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="qwen2.5:latest",
        help="Local Ollama model name for hook generation (default: qwen2.5:latest)"
    )
    args = parser.parse_args()
    
    # 1. Verify input frame strictly
    if not os.path.exists(INPUT_FRAME):
        raise FileNotFoundError(f"Input frame not found at: {INPUT_FRAME}. Please place a base image in inputs/")
    base_image = Image.open(INPUT_FRAME).convert("RGB")
    print(f"[Input] Loaded base frame: {INPUT_FRAME} (Size: {base_image.size})")
    
    # 2. Query local Ollama dynamically for hooks based on user's tagline
    hooks = query_ollama_hooks(args.tagline, model_name=args.model)
    
    # 3. Load Qwen-Image-2.1-Turbo pipeline
    pipe = load_pipeline()
    
    # 4. Generate 4 image variations strictly using QwenImage21Pipeline
    variations = []
    for idx, hook in enumerate(hooks, 1):
        prompt = (
            f"A high-impact cinematic YouTube video thumbnail based on the scene. "
            f"Bold visual focus, striking lighting, modern typography style element: \"{hook}\". "
            f"High contrast, professional 2K creator production quality."
        )
        print(f"\n[Qwen 2.1 Turbo] Generating variation {idx}/4: \"{hook}\"")
        image = pipe(
            prompt=prompt,
            image=base_image,
            width=1280,
            height=720,
            use_kv_cache=True,
            generator=torch.Generator("cuda" if torch.cuda.is_available() else "cpu").manual_seed(42 + idx * 100),
        ).images[0]
        variations.append(image)
        
    # 5. Build and save the 2x2 comparison grid
    stitch_ab_grid(variations)

if __name__ == "__main__":
    main()
