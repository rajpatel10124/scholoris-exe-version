import os
import sys

# We want to download the models into a local 'offline_models' folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, 'offline_models')
os.makedirs(MODELS_DIR, exist_ok=True)

# 1. Set environment variables to force huggingface to use this folder
os.environ['HF_HOME'] = MODELS_DIR
os.environ['SENTENCE_TRANSFORMERS_HOME'] = MODELS_DIR

print(f"Downloading models into: {MODELS_DIR}")
print("This may take a few minutes...\n")

# 2. Download NLTK Data
print("Downloading NLTK data...")
import nltk
nltk_data_dir = os.path.join(MODELS_DIR, 'nltk_data')
os.makedirs(nltk_data_dir, exist_ok=True)
nltk.data.path.append(nltk_data_dir)
for pkg in ['punkt', 'stopwords']:
    nltk.download(pkg, download_dir=nltk_data_dir)

# 3. Download SentenceTransformer (all-mpnet-base-v2 matching logic.py exactly)
print("\nDownloading SentenceTransformer (sentence-transformers/all-mpnet-base-v2)...")
from sentence_transformers import SentenceTransformer
st_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

# 4. Download CrossEncoder
print("\nDownloading CrossEncoder (ms-marco-MiniLM-L-6-v2)...")
from sentence_transformers import CrossEncoder
cross_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

# 5. Download GPT2 for AI Detection (essential for offline AI checks)
print("\nDownloading GPT-2 Model and Tokenizer for AI detection...")
from transformers import AutoTokenizer, AutoModelForCausalLM
gpt2_tok = AutoTokenizer.from_pretrained("gpt2")
gpt2_model = AutoModelForCausalLM.from_pretrained("gpt2")

# 6. Download TrOCR for Handwritten OCR (essential for offline handwriting checks)
print("\nDownloading TrOCR Model and Processor for handwriting OCR...")
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
trocr_proc = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
trocr_model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")

print("\n✅ All models downloaded successfully into 'offline_models'!")
print("You can now build the desktop app.")
