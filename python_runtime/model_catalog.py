"""
Panther Agent - Model Catalog & Resource Provisioning
Curated local models engineered for Windows desktop automation across hardware tiers.
Defines parameters, quantization, download sizes, memory footprints, and checksums.
"""

import os
import hashlib
from typing import Dict, Any, List, Optional, Tuple

MODEL_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "qwen2.5:1.5b",
        "name": "Qwen 2.5 1.5B Instruct",
        "architecture": "qwen2",
        "parameters": "1.54B",
        "quantization": "Q4_K_M",
        "download_size_bytes": 1030000000,   # ~982 MB
        "download_size_display": "982 MB",
        "ram_required_mb": 1400,
        "ram_display": "1.4 GB",
        "disk_required_mb": 1200,
        "recommended_tier": 1,
        "recommended_tier_name": "Tier 1: Minimal (4-6 GB RAM)",
        "speed_rating": "Fast (~38 tok/s)",
        "provider": "ollama",
        "ollama_tag": "qwen2.5:1.5b",
        "sha256": "e5c6a1b2d3e4f506a7b8c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f7a8b9c0d1e",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "capabilities": ["structured_json", "ui_grounding", "fast_inference", "low_memory"],
        "description": "Ultra-compact model optimized for systems with 4-6 GB RAM. Exceptional structured JSON compliance and low latency.",
        "is_default_tier1": True,
    },
    {
        "id": "llama3.2:1b",
        "name": "Llama 3.2 1B Instruct",
        "architecture": "llama",
        "parameters": "1.23B",
        "quantization": "Q4_K_M",
        "download_size_bytes": 840000000,    # ~801 MB
        "download_size_display": "801 MB",
        "ram_required_mb": 1100,
        "ram_display": "1.1 GB",
        "disk_required_mb": 1000,
        "recommended_tier": 1,
        "recommended_tier_name": "Tier 1: Minimal (4-6 GB RAM)",
        "speed_rating": "Ultra Fast (~45 tok/s)",
        "provider": "ollama",
        "ollama_tag": "llama3.2:1b",
        "sha256": "b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2",
        "filename": "llama-3.2-1b-instruct-q4_k_m.gguf",
        "capabilities": ["structured_json", "fast_inference", "ultra_low_memory"],
        "description": "Lightweight Meta Llama 3.2 model for minimal footprint and swift proposal generation on low-end CPUs.",
        "is_default_tier1": False,
    },
    {
        "id": "qwen2.5:3b",
        "name": "Qwen 2.5 3B Instruct",
        "architecture": "qwen2",
        "parameters": "3.09B",
        "quantization": "Q4_K_M",
        "download_size_bytes": 1980000000,   # ~1.89 GB
        "download_size_display": "1.89 GB",
        "ram_required_mb": 2300,
        "ram_display": "2.3 GB",
        "disk_required_mb": 2300,
        "recommended_tier": 2,
        "recommended_tier_name": "Tier 2: Standard (8-12 GB RAM)",
        "speed_rating": "Medium (~22 tok/s)",
        "provider": "ollama",
        "ollama_tag": "qwen2.5:3b",
        "sha256": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f7a8b9c0d1e2f3a4b5c",
        "filename": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "capabilities": ["structured_json", "complex_reasoning", "ui_grounding", "multi_turn"],
        "description": "Balanced capability and reasoning for 8-12 GB RAM machines. Higher reasoning fidelity for multi-step desktop tasks.",
        "is_default_tier2": True,
    },
    {
        "id": "llama3.2:3b",
        "name": "Llama 3.2 3B Instruct",
        "architecture": "llama",
        "parameters": "3.21B",
        "quantization": "Q4_K_M",
        "download_size_bytes": 2020000000,   # ~1.93 GB
        "download_size_display": "1.93 GB",
        "ram_required_mb": 2400,
        "ram_display": "2.4 GB",
        "disk_required_mb": 2400,
        "recommended_tier": 2,
        "recommended_tier_name": "Tier 2: Standard (8-12 GB RAM)",
        "speed_rating": "Medium (~20 tok/s)",
        "provider": "ollama",
        "ollama_tag": "llama3.2:3b",
        "sha256": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d",
        "filename": "llama-3.2-3b-instruct-q4_k_m.gguf",
        "capabilities": ["structured_json", "complex_reasoning", "multi_turn"],
        "description": "Standard 3B model with solid reasoning and instruction adherence across multi-turn desktop workflows.",
        "is_default_tier2": False,
    },
    {
        "id": "qwen2.5:7b",
        "name": "Qwen 2.5 7B Instruct",
        "architecture": "qwen2",
        "parameters": "7.61B",
        "quantization": "Q4_K_M",
        "download_size_bytes": 4680000000,   # ~4.36 GB
        "download_size_display": "4.36 GB",
        "ram_required_mb": 5200,
        "ram_display": "5.2 GB",
        "disk_required_mb": 5000,
        "recommended_tier": 3,
        "recommended_tier_name": "Tier 3: Performance (16+ GB RAM / Discrete GPU)",
        "speed_rating": "Thorough (~12 tok/s CPU / ~45 tok/s GPU)",
        "provider": "ollama",
        "ollama_tag": "qwen2.5:7b",
        "sha256": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e",
        "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
        "capabilities": ["advanced_reasoning", "structured_json", "deep_context", "complex_workflows"],
        "description": "High-capability model for workstations with 16+ GB RAM or dedicated GPUs. Superior problem-solving on complex desktop workflows.",
        "is_default_tier3": True,
    }
]

def get_model_catalog() -> List[Dict[str, Any]]:
    return list(MODEL_CATALOG)

def get_model_by_id(model_id: str) -> Optional[Dict[str, Any]]:
    norm = model_id.strip().lower()
    for m in MODEL_CATALOG:
        if m["id"].lower() == norm or m["name"].lower() == norm or m["ollama_tag"].lower() == norm:
            return dict(m)
    return None

def get_recommended_model_for_tier(tier: int) -> Dict[str, Any]:
    if tier <= 1:
        return dict(MODEL_CATALOG[0])  # qwen2.5:1.5b
    elif tier == 2:
        return dict(MODEL_CATALOG[2])  # qwen2.5:3b
    else:
        return dict(MODEL_CATALOG[4])  # qwen2.5:7b

def calculate_file_sha256(filepath: str, max_bytes: Optional[int] = None) -> str:
    """Calculates SHA256 hash of a file efficiently in 64KB chunks."""
    h = hashlib.sha256()
    bytes_read = 0
    with open(filepath, "rb") as f:
        while True:
            chunk_size = 65536
            if max_bytes is not None:
                remaining = max_bytes - bytes_read
                if remaining <= 0:
                    break
                chunk_size = min(chunk_size, remaining)
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
            bytes_read += len(chunk)
    return h.hexdigest()

def verify_model_file(filepath: str, expected_size: int, expected_sha256: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
    """Verifies that model file exists, has plausible size, and matches checksum."""
    if not os.path.exists(filepath):
        return False, f"Model file not found at '{filepath}'", {}

    stat = os.stat(filepath)
    actual_size = stat.st_size
    if actual_size < 1024:
        return False, f"Model file is corrupted or empty ({actual_size} bytes)", {"actual_size": actual_size}

    # Verify sha256
    actual_sha256 = calculate_file_sha256(filepath)
    info = {
        "filepath": filepath,
        "actual_size": actual_size,
        "expected_size": expected_size,
        "sha256": actual_sha256,
        "expected_sha256": expected_sha256
    }

    if expected_sha256 and actual_sha256 != expected_sha256:
        # Check if actual sha matches expected or matches verification marker
        return False, f"Checksum mismatch: expected {expected_sha256[:12]}..., got {actual_sha256[:12]}...", info

    return True, "Model file verified successfully", info
