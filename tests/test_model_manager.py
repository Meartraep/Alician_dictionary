import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_settings import AppSettings
import model_manager
from webui_backend import similarity_matcher


class ModelManagerTests(unittest.TestCase):
    def test_runtime_metadata_matches_packaging_manifest(self):
        manifest_path = Path(__file__).resolve().parents[1] / "installer" / "model_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["model"], model_manager.MODEL_NAME)
        self.assertEqual(manifest["revision"], model_manager.MODEL_REVISION)
        self.assertEqual(manifest["files"], model_manager.MODEL_FILES)

    def test_model_validation_checks_size_and_hash(self):
        content = b"pinned model data"
        metadata = {
            "model.bin": {
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            model_file = Path(directory) / "model.bin"
            model_file.write_bytes(content)
            with patch.object(model_manager, "MODEL_FILES", metadata):
                self.assertTrue(
                    model_manager.validate_model_path(directory, verify_hashes=True)["ok"]
                )
                model_file.write_bytes(b"corrupted model")
                self.assertFalse(
                    model_manager.validate_model_path(directory, verify_hashes=True)["ok"]
                )

    def test_saved_model_path_survives_when_there_is_no_installer_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_path = root / "app_settings.json"
            settings_path.write_text(
                json.dumps({"model_path": str(root / "custom-model")}),
                encoding="utf-8",
            )
            db_path = root / "translated.db"
            db_path.write_bytes(b"db")
            settings = AppSettings(
                settings_path,
                db_path,
                default_model_path=str(root / "default-model"),
            )
            self.assertEqual(
                settings.settings["model_path"], str(root / "custom-model")
            )

    def test_installer_model_path_overrides_an_old_saved_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_path = root / "app_settings.json"
            settings_path.write_text(
                json.dumps({"model_path": str(root / "old-model")}),
                encoding="utf-8",
            )
            db_path = root / "translated.db"
            db_path.write_bytes(b"db")
            selected_path = str(root / "installer-selected-model")
            settings = AppSettings(
                settings_path,
                db_path,
                default_model_path=selected_path,
                prefer_default_model_path=True,
            )
            self.assertEqual(settings.settings["model_path"], selected_path)

    def test_frozen_build_does_not_fall_back_to_network_model_name(self):
        configured_path = r"D:\models\text2vec-base-chinese"
        with patch.dict(
            os.environ,
            {model_manager.MODEL_ENVIRONMENT_VARIABLE: configured_path},
            clear=False,
        ):
            self.assertEqual(similarity_matcher._model_path(), configured_path)


if __name__ == "__main__":
    unittest.main()
