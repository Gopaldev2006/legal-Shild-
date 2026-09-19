import os

# Training & LoRA Hyperparameter Configuration
BASE_MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
DATASET_DIR = os.path.join(os.path.dirname(__file__), "datasets")
CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
EVAL_DIR = os.path.join(os.path.dirname(__file__), "evaluation")

# LoRA / PEFT Parameters
LORA_R = 8
LORA_ALPHA = 16
LORA_DROPOUT = 0.05
TARGET_MODULES = ["q_proj", "v_proj", "k_proj", "o_proj"]

# Hyperparameters
LEARNING_RATE = 2e-4
NUM_EPOCHS = 3
BATCH_SIZE = 2
GRADIENT_ACCUMULATION_STEPS = 4
MAX_SEQ_LENGTH = 512
DEVICE = "cpu"  # Auto GPU fallback supported
