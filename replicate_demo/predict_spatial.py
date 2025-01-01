# Prediction interface for Cog ⚙️
# https://cog.run/python

import os
import subprocess
import time
from cog import BasePredictor, Input, Path
import torch
from PIL import Image
from diffusers.pipelines import FluxPipeline
from src.flux.condition import Condition
from src.flux.generate import generate, seed_everything


MODEL_CACHE = "model_sp"
MODEL_URL = "https://weights.replicate.delivery/default/Yuanshi/OminiControl/model_cache_spatial.tar"


def download_weights(url, dest):
    start = time.time()
    print("downloading url: ", url)
    print("downloading to: ", dest)
    subprocess.check_call(["pget", "-x", url, dest], close_fds=False)
    print("downloading took: ", time.time() - start)


class Predictor(BasePredictor):
    def setup(self) -> None:
        """Load the model into memory to make running multiple predictions efficient"""

        if not os.path.exists(MODEL_CACHE):
            print("downloading")
            download_weights(MODEL_URL, MODEL_CACHE)

        self.pipe = FluxPipeline.from_pretrained(
            f"{MODEL_CACHE}/black-forest-labs/FLUX.1-dev",
            torch_dtype=torch.bfloat16,
        ).to("cuda")
        for adapter_name in ["fill", "canny", "depth", "coloring", "deblurring"]:
            self.pipe.load_lora_weights(
                f"{MODEL_CACHE}/Yuanshi/OminiControl",
                weight_name=f"experimental/{adapter_name}.safetensors",
                adapter_name=adapter_name,
            )

    def predict(
        self,
        model: str = Input(
            description="Choose a task",
            choices=[
                "fill",
                "canny",
                "depth",
                "coloring",
                "deblurring",
            ],
            default="fill",
        ),
        prompt: str = Input(
            description="Input prompt.",
            default="The Mona Lisa is wearing a white VR headset with 'Omini' written on it.",
        ),
        image: Path = Input(description="Input image"),
        num_inference_steps: int = Input(
            description="Number of denoising steps", ge=1, le=500, default=50
        ),
        guidance_scale: float = Input(
            description="Scale for classifier-free guidance", ge=1, le=20, default=7.5
        ),
        seed: int = Input(
            description="Random seed. Leave blank to randomize the seed", default=None
        ),
    ) -> Path:
        """Run a single prediction on the model"""

        (width, height) = (512, 512)
        image = Image.open(str(image)).convert("RGB").resize((width, height))

        if seed is None:
            seed = int.from_bytes(os.urandom(2), "big")
        print(f"Using seed: {seed}")

        seed_everything(seed)
        generator = torch.Generator("cuda").manual_seed(seed)
        condition = Condition(model.split("_")[0], image)

        result_img = generate(
            self.pipe,
            prompt=prompt,
            conditions=[condition],
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            height=height,
            width=width,
            generator=generator,
        ).images[0]

        # out_path = "/tmp/out.png"
        out_path = "out.png"
        result_img.save(out_path)
        return Path(out_path)