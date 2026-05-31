from huggingface_hub import hf_hub_download
import os

print("--- Retrying Model Weight Download ---")
try:
    print("Downloading pytorch_model.bin (this is large, ~600MB)...")
    hf_hub_download(repo_id="openai/clip-vit-base-patch32", filename="pytorch_model.bin")
    print("Download complete!")
except Exception as e:
    print(f"Download failed: {e}")
