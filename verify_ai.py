import os
import sys

# Set cache before importing transformers
os.environ['TRANSFORMERS_CACHE'] = 'C:\\tmp\\huggingface_cache'

try:
    from app import is_image_relevant
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test_image(image_path, expected_relevant):
    print(f"Testing image: {image_path}")
    try:
        result = is_image_relevant(image_path)
        print(f"Result: {'RELEVANT' if result else 'SPAM'}")
        if result == expected_relevant:
            print("✅ Correct!")
        else:
            print("❌ Incorrect!")
    except Exception as e:
        print(f"Error testing image: {e}")

if __name__ == "__main__":
    pothole_path = r'C:\Users\krish\.gemini\antigravity\brain\8e686a9d-76c3-4967-ae67-e5ede7e6d048\pothole_test_1775237969437.png'
    cat_path = r'C:\Users\krish\.gemini\antigravity\brain\8e686a9d-76c3-4967-ae67-e5ede7e6d048\cat_test_1775237985785.png'
    
    print("--- Verifying AI Detection ---")
    test_image(pothole_path, True)
    test_image(cat_path, False)
