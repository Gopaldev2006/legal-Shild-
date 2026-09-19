import os
import json
import pytest
from app.core.config import settings
from app.services.rag.providers.local_slm_provider import LocalSLMProvider
from training.prepare_dataset import prepare_and_split_dataset
from training.train_slm import run_lora_fine_tuning
from training.evaluate_slm import evaluate_baseline_vs_finetuned, LEGAL_FINE_TUNING_DISCLAIMER


def test_dataset_preparation(tmp_path):
    output_dir = str(tmp_path / "test_datasets")
    res = prepare_and_split_dataset(output_dir=output_dir)

    assert os.path.exists(res["train"])
    assert os.path.exists(res["val"])

    with open(res["train"], "r", encoding="utf-8") as f:
        train_items = json.load(f)
        assert len(train_items) > 0
        assert "instruction" in train_items[0]
        assert "context" in train_items[0]
        assert "response" in train_items[0]


def test_lora_fine_tuning_execution(tmp_path):
    output_dir = str(tmp_path / "test_checkpoints" / "best_adapter")
    res = run_lora_fine_tuning(output_dir=output_dir)

    assert res["status"] == "success"
    assert os.path.exists(res["config_file"])
    assert os.path.exists(res["weights_file"])

    with open(res["config_file"], "r", encoding="utf-8") as f:
        config_data = json.load(f)
        assert config_data["peft_type"] == "LORA"
        assert config_data["r"] == 8
        assert config_data["lora_alpha"] == 16


def test_baseline_vs_finetuned_evaluation(tmp_path):
    eval_file = str(tmp_path / "test_eval_report.json")
    report = evaluate_baseline_vs_finetuned(eval_output_file=eval_file)

    assert os.path.exists(eval_file)
    assert "baseline_model" in report
    assert "finetuned_model" in report
    assert "performance_gain" in report

    assert report["baseline_model"]["perplexity"] > report["finetuned_model"]["perplexity"]
    assert report["finetuned_model"]["qualitative_alignment_score"] > report["baseline_model"]["qualitative_alignment_score"]


def test_model_selection_toggle_config():
    # 1. Base Model Provider
    base_provider = LocalSLMProvider(use_finetuned=False)
    assert "Base Model" in base_provider.provider_name
    health_base = base_provider.get_health()
    assert health_base["model_selection"] == "Base Model"

    # 2. Fine-Tuned LoRA Provider
    ft_provider = LocalSLMProvider(use_finetuned=True, adapter_path="training/checkpoints/best_adapter")
    assert "Fine-Tuned LoRA" in ft_provider.provider_name
    health_ft = ft_provider.get_health()
    assert health_ft["model_selection"] == "Fine-Tuned Adapter"
    assert health_ft["adapter_path"] == "training/checkpoints/best_adapter"


def test_disclaimer_and_limitations_reporting():
    assert "does NOT guarantee legal accuracy" in LEGAL_FINE_TUNING_DISCLAIMER
    assert "Grounded RAG security checks remain mandatory" in LEGAL_FINE_TUNING_DISCLAIMER
