"""
Panther Agent - Stage 3 Automated Test Suite
Validates Device Discovery, Capability Detection, Tier Assignment,
Model Catalog, Setup State Machine Transitions, Checkpoint Resumption,
and Deterministic Inference Benchmarking.
"""

import os
import sys
import tempfile
import unittest
import time
import json
from unittest.mock import patch, MagicMock

pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

from database import DatabaseManager
from config_manager import ConfigManager
from device_manager import DeviceManager
from model_manager import ModelManager
from setup_manager import SetupManager, SetupState
from model_catalog import (
    MODEL_CATALOG,
    get_model_catalog,
    get_model_by_id,
    get_recommended_model_for_tier,
    calculate_file_sha256,
    verify_model_file
)

class TestStage3DeviceDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_panther.db")
        self.db = DatabaseManager(self.db_path)
        self.device = DeviceManager(self.db)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_complete_device_profile_schema(self):
        """Validates that inspect_device returns all mandatory discovery telemetry."""
        profile = self.device.inspect_device(force_refresh=True)

        self.assertIn("id", profile)
        self.assertIn("hostname", profile)
        self.assertIn("os", profile)
        self.assertIn("cpu", profile)
        self.assertIn("memory", profile)
        self.assertIn("gpu", profile)
        self.assertIn("display", profile)
        self.assertIn("storage", profile)
        self.assertIn("capabilities", profile)
        self.assertIn("tier", profile)
        self.assertIn("tier_name", profile)
        self.assertIn("recommended_model_id", profile)
        self.assertIn("meets_minimum_requirements", profile)

        # OS schema checks
        os_info = profile["os"]
        self.assertIsInstance(os_info["name"], str)
        self.assertIn(os_info["architecture"], ["x64", "x86", "arm64"])
        self.assertIsInstance(os_info["is_64bit"], bool)
        self.assertIn("windows_capabilities", os_info)

        # CPU schema checks
        cpu = profile["cpu"]
        self.assertGreaterEqual(cpu["physical_cores"], 1)
        self.assertGreaterEqual(cpu["logical_processors"], 1)
        self.assertIsInstance(cpu["name"], str)
        self.assertIsInstance(cpu["features"], list)
        self.assertGreater(cpu["current_usage_percent"], 0)

        # Memory schema checks
        mem = profile["memory"]
        self.assertGreater(mem["total_mb"], 512)
        self.assertGreater(mem["available_mb"], 0)
        self.assertIn(mem["system_memory_pressure"], ["NORMAL", "MODERATE", "HIGH", "CRITICAL"])

        # Display schema checks
        disp = profile["display"]
        self.assertGreaterEqual(disp["width"], 640)
        self.assertGreaterEqual(disp["height"], 480)
        self.assertGreater(disp["dpi_scale"], 0.5)

        # Storage schema checks
        storage = profile["storage"]
        self.assertGreater(storage["total_mb"], 1000)
        self.assertGreater(storage["available_mb"], 0)
        self.assertIsInstance(storage["adequate_for_models"], bool)

        # Capabilities check
        caps = profile["capabilities"]
        self.assertTrue(caps["screen_capture"])
        self.assertTrue(caps["input"])
        self.assertIn("network", caps)

    def test_deterministic_tier_assignment(self):
        """Validates hardware tier classification logic across 4GB, 8GB, and 16GB machines."""
        # Tier 1 Minimal profile: 4GB RAM, 2 cores, integrated GPU
        mem_t1 = {"total_mb": 4096, "available_mb": 2500}
        cpu_t1 = {"logical_processors": 2}
        gpu_t1 = {"has_discrete_gpu": False, "vram_mb": 0}
        storage_t1 = {"available_mb": 30000}
        caps_t1 = {"screen_capture": True}
        t1 = self.device._assign_tier(mem_t1, cpu_t1, gpu_t1, storage_t1, caps_t1)
        self.assertEqual(t1["tier"], 1)
        self.assertEqual(t1["recommended_model_id"], "qwen2.5:1.5b")
        self.assertTrue(t1["meets_minimum_requirements"])

        # Tier 2 Standard profile: 8GB RAM, 4 cores, integrated GPU
        mem_t2 = {"total_mb": 8192, "available_mb": 5000}
        cpu_t2 = {"logical_processors": 4}
        gpu_t2 = {"has_discrete_gpu": False, "vram_mb": 0}
        t2 = self.device._assign_tier(mem_t2, cpu_t2, gpu_t2, storage_t1, caps_t1)
        self.assertEqual(t2["tier"], 2)
        self.assertEqual(t2["recommended_model_id"], "qwen2.5:3b")

        # Tier 3 Performance profile: 16GB RAM, 8 cores, discrete GPU
        mem_t3 = {"total_mb": 16384, "available_mb": 12000}
        cpu_t3 = {"logical_processors": 8}
        gpu_t3 = {"has_discrete_gpu": True, "vram_mb": 6000}
        t3 = self.device._assign_tier(mem_t3, cpu_t3, gpu_t3, storage_t1, caps_t1)
        self.assertEqual(t3["tier"], 3)
        self.assertEqual(t3["recommended_model_id"], "qwen2.5:7b")

class TestStage3ModelCatalog(unittest.TestCase):
    def test_catalog_integrity(self):
        """Validates all model definitions have complete metadata, sizes, and SHA256 hashes."""
        catalog = get_model_catalog()
        self.assertGreaterEqual(len(catalog), 3)

        for m in catalog:
            self.assertIn("id", m)
            self.assertIn("name", m)
            self.assertIn("parameters", m)
            self.assertIn("quantization", m)
            self.assertGreater(m["download_size_bytes"], 100000000)
            self.assertGreater(m["ram_required_mb"], 500)
            self.assertEqual(len(m["sha256"]), 64)  # Standard SHA256 hex string length
            self.assertIn(m["recommended_tier"], [1, 2, 3])
            self.assertIsInstance(m["capabilities"], list)

    def test_model_catalog_lookups(self):
        m1 = get_model_by_id("qwen2.5:1.5b")
        self.assertIsNotNone(m1)
        self.assertEqual(m1["recommended_tier"], 1)

        m2 = get_model_by_id("qwen2.5:3b")
        self.assertIsNotNone(m2)
        self.assertEqual(m2["recommended_tier"], 2)

        rec1 = get_recommended_model_for_tier(1)
        self.assertEqual(rec1["id"], "qwen2.5:1.5b")

        rec2 = get_recommended_model_for_tier(2)
        self.assertEqual(rec2["id"], "qwen2.5:3b")

        rec3 = get_recommended_model_for_tier(3)
        self.assertEqual(rec3["id"], "qwen2.5:7b")

class TestStage3SetupStateMachine(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_panther.db")
        self.db = DatabaseManager(self.db_path)
        self.config = ConfigManager(self.db)
        self.device = DeviceManager(self.db)
        self.model = ModelManager(self.db, self.config)
        self.setup = SetupManager(self.db, self.config, self.device, self.model)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_initial_state_not_started(self):
        """On clean installation, setup state must be NOT_STARTED."""
        status = self.setup.get_setup_status()
        self.assertEqual(status["current_state"], SetupState.NOT_STARTED)
        self.assertFalse(status["ready"])
        self.assertFalse(status["completed"])

    def test_scan_transitions_to_waiting_for_model(self):
        """Scanning hardware moves through SCANNING -> ANALYZING -> WAITING_FOR_MODEL_SELECTION."""
        status = self.setup.scan_device_and_capabilities()
        self.assertEqual(status["current_state"], SetupState.WAITING_FOR_MODEL_SELECTION)
        self.assertIsNotNone(status["profile"])
        self.assertIn("tier", status)

    def test_illegal_state_transition_blocked(self):
        """Enforces that skipping states (e.g. NOT_STARTED -> CONFIGURING_RUNTIME) is blocked."""
        success = self.setup._transition_to(SetupState.CONFIGURING_RUNTIME)
        self.assertFalse(success)
        self.assertEqual(self.setup._session["current_state"], SetupState.NOT_STARTED)

    def test_model_selection(self):
        """User model selection is stored and validated against the verified catalog."""
        self.setup.scan_device_and_capabilities()
        status = self.setup.select_model("qwen2.5:3b")
        self.assertEqual(status["selected_model"], "qwen2.5:3b")
        self.assertEqual(self.config.get_value("model", "selected_model"), "qwen2.5:3b")

        # Unknown model rejected
        with self.assertRaises(ValueError):
            self.setup.select_model("unsupported-giant-model:70b")

    def test_checkpoint_persistence_and_resumption(self):
        """Validates that setup state and checkpoints survive restart."""
        self.setup.scan_device_and_capabilities()
        self.setup.select_model("llama3.2:1b")

        # Simulate application restart with new SetupManager instance
        new_setup = SetupManager(self.db, self.config, self.device, self.model)
        status = new_setup.get_setup_status()
        self.assertEqual(status["current_state"], SetupState.WAITING_FOR_MODEL_SELECTION)
        self.assertEqual(status["selected_model"], "llama3.2:1b")

    def test_deterministic_inference_benchmark(self):
        """Validates the inference benchmark runs, measures latency, and tests action schema."""
        model_meta = get_model_by_id("qwen2.5:1.5b")
        bench_result = self.setup._run_inference_benchmark(model_meta)

        self.assertTrue(bench_result["passed"])
        self.assertGreater(bench_result["latency_ms"], 0)
        self.assertIn("action_proposed", bench_result)
        self.assertIn("tested_at", bench_result)

    def test_full_setup_completion_flow(self):
        """Executes full setup flow: scan -> select -> download -> verify -> test -> ready."""
        # 1. Scan
        self.setup.scan_device_and_capabilities()
        self.assertEqual(self.setup._session["current_state"], SetupState.WAITING_FOR_MODEL_SELECTION)

        # 2. Select
        self.setup.select_model("qwen2.5:1.5b")

        # 3. Provision & Verify
        status = self.setup.verify_and_test_model()
        self.assertEqual(status["current_state"], SetupState.READY)
        self.assertTrue(status["ready"])
        self.assertTrue(status["completed"])

        # Verify config was updated with tier-appropriate settings
        tier = status["tier"]
        res_limits = self.config.get_section("resource_limits")
        self.assertIn("min_available_ram_mb", res_limits)
        self.assertTrue(self.config.get_value("installation", "setup_completed"))

if __name__ == "__main__":
    unittest.main()
