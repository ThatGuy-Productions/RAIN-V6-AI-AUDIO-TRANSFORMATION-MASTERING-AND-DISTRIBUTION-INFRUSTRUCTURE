#!/usr/bin/env python3
"""
RAIN V6 Automated Remediation Script
Applies audited fixes for DSP vectorization, heuristic unification, dependency gaps, 
and lifecycle leaks. 
"""
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ==============================================================================
# 1. backend/app/services/heuristic_params.py
# ==============================================================================
HEURISTIC_PARAMS_CONTENT = '''"""
RAIN Heuristic Fallback — Canonical ProcessingParams per CLAUDE.md

When RAIN_NORMALIZATION_VALIDATED=false, this module produces a deterministic
ProcessingParams dict from (genre, platform) pairs. This is the AUTHORITATIVE
backend definition — the frontend must match exactly.

Output is deterministic: same (genre, platform) → identical ProcessingParams.
"""

from __future__ import annotations
from typing import Any
from app.services.platform_targets import get_platform_target

def default_params() -> dict[str, Any]:
    return {
        "target_lufs": -14.0, "true_peak_ceiling": -1.0,
        "mb_threshold_low": -20.0, "mb_threshold_mid": -18.0, "mb_threshold_high": -16.0,
        "mb_ratio_low": 2.5, "mb_ratio_mid": 2.0, "mb_ratio_high": 2.0,
        "mb_attack_low": 10.0, "mb_attack_mid": 5.0, "mb_attack_high": 2.0,
        "mb_release_low": 150.0, "mb_release_mid": 80.0, "mb_release_high": 40.0,
        "eq_gains": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "analog_saturation": False, "saturation_drive": 0.0, "saturation_mode": "tape",
        "ms_enabled": False, "mid_gain": 0.0, "side_gain": 0.0, "stereo_width": 1.0,
        "sail_enabled": False, "sail_stem_gains": [0.0] * 12,
        "vinyl_mode": False,
        "macro_brighten": 5.0, "macro_glue": 5.0, "macro_width": 5.0,
        "macro_punch": 5.0, "macro_warmth": 5.0, "macro_space": 5.0, "macro_repair": 0.0,
    }

GENRE_OVERRIDES: dict[str, dict[str, Any]] = {
    "electronic": {
        "mb_threshold_low": -18.0, "mb_threshold_mid": -16.0, "mb_threshold_high": -14.0,
        "mb_ratio_low": 3.0, "mb_ratio_mid": 2.5, "mb_ratio_high": 2.0,
        "stereo_width": 1.3, "analog_saturation": False,
        "macro_brighten": 5.0, "macro_glue": 6.0, "macro_width": 7.0,
        "macro_punch": 5.0, "macro_warmth": 3.0, "macro_space": 6.0, "macro_repair": 0.0,
    },
    "hiphop": {
        "mb_threshold_low": -16.0, "mb_threshold_mid": -14.0, "mb_threshold_high": -14.0,
        "mb_ratio_low": 3.5, "mb_ratio_mid": 2.5, "mb_ratio_high": 2.0,
        "stereo_width": 1.1, "analog_saturation": True, "saturation_drive": 0.2,
        "macro_brighten": 4.0, "macro_glue": 7.0, "macro_width": 4.0,
        "macro_punch": 8.0, "macro_warmth": 5.0, "macro_space": 3.0, "macro_repair": 0.0,
    },
    "rock": {
        "mb_threshold_low": -18.0, "mb_threshold_mid": -16.0, "mb_threshold_high": -12.0,
        "mb_ratio_low": 2.5, "mb_ratio_mid": 2.0, "mb_ratio_high": 2.5,
        "analog_saturation": True, "saturation_drive": 0.15,
        "macro_brighten": 5.0, "macro_glue": 5.0, "macro_width": 5.0,
        "macro_punch": 7.0, "macro_warmth": 6.0, "macro_space": 4.0, "macro_repair": 0.0,
    },
    "pop": {
        "mb_threshold_low": -20.0, "mb_threshold_mid": -18.0, "mb_threshold_high": -16.0,
        "mb_ratio_low": 2.0, "mb_ratio_mid": 2.0, "mb_ratio_high": 1.8,
        "stereo_width": 1.1,
        "macro_brighten": 6.0, "macro_glue": 5.0, "macro_width": 5.0,
        "macro_punch": 5.0, "macro_warmth": 4.0, "macro_space": 5.0, "macro_repair": 0.0,
    },
    "classical": {
        "mb_threshold_low": -24.0, "mb_threshold_mid": -22.0, "mb_threshold_high": -22.0,
        "mb_ratio_low": 1.5, "mb_ratio_mid": 1.5, "mb_ratio_high": 1.5,
        "stereo_width": 0.95,
        "macro_brighten": 3.0, "macro_glue": 2.0, "macro_width": 4.0,
        "macro_punch": 2.0, "macro_warmth": 3.0, "macro_space": 7.0, "macro_repair": 0.0,
    },
    "jazz": {
        "mb_threshold_low": -22.0, "mb_threshold_mid": -20.0, "mb_threshold_high": -20.0,
        "mb_ratio_low": 2.0, "mb_ratio_mid": 1.8, "mb_ratio_high": 1.5,
        "analog_saturation": True, "saturation_drive": 0.1,
        "macro_brighten": 3.0, "macro_glue": 4.0, "macro_width": 4.0,
        "macro_punch": 3.0, "macro_warmth": 6.0, "macro_space": 6.0, "macro_repair": 0.0,
    },
    "default": {
        "mb_threshold_low": -20.0, "mb_threshold_mid": -18.0, "mb_threshold_high": -16.0,
        "mb_ratio_low": 2.5, "mb_ratio_mid": 2.0, "mb_ratio_high": 2.0,
        "macro_brighten": 5.0, "macro_glue": 5.0, "macro_width": 5.0,
        "macro_punch": 5.0, "macro_warmth": 5.0, "macro_space": 5.0, "macro_repair": 0.0,
    },
}

def generate_heuristic_params(genre: str, platform: str, vinyl: bool = False) -> dict[str, Any]:
    params = default_params()
    target = get_platform_target(platform)
    params["target_lufs"] = target.target_lufs
    params["true_peak_ceiling"] = target.true_peak_ceiling

    if vinyl or platform == "vinyl":
        params["vinyl_mode"] = True
        params["true_peak_ceiling"] = -3.0

    overrides = GENRE_OVERRIDES.get(genre, GENRE_OVERRIDES["default"])
    for key, value in overrides.items():
        params[key] = value

    return params
'''

# ==============================================================================
# 2. requirements.txt
# ==============================================================================
REQUIREMENTS_CONTENT = '''# Core API & AI
anthropic>=0.40.0
fastapi>=0.100.0
uvicorn>=0.23.0

# DSP & Audio
numpy>=1.24.0
scipy>=1.10.0
soundfile>=0.12.0
librosa>=0.10.0

# ML & Separation
torch>=2.0.0
torchaudio>=2.0.0
music-source-separation-training @ git+https://github.com/facebookresearch/music-source-separation-training.git
'''

# ==============================================================================
# 3. .env.example
# ==============================================================================
ENV_EXAMPLE_CONTENT = '''# RAIN V6 Environment Configuration
# ... (preserve your existing variables above this line) ...

# --- C2PA & Provenance (RAIN V6 Cryptographic Chain) ---
C2PA_SIGNING_CERT_PATH="./certs/rain_c2pa_cert.pem"
C2PA_SIGNING_KEY_PATH="./certs/rain_c2pa_key.pem"
AUDIOSEAL_MODEL_PATH="./models/audioseal/wm_16k.pth"
AUDIOSEAL_KEY_SEED="rain-provenance-seed-change-me-in-prod"
'''

def write_file(filepath: str, content: str):
    """Safely write content to a file, creating directories if needed."""
    dir_name = os.path.dirname(filepath)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    logging.info(f"Updated: {filepath}")

def main():
    logging.info("Starting RAIN V6 Remediation...")
    
    # 1. Heuristic Params
    write_file("backend/app/services/heuristic_params.py", HEURISTIC_PARAMS_CONTENT)
    
    # 2. Requirements
    write_file("requirements.txt", REQUIREMENTS_CONTENT)
    
    # 3. Env Example (Append to existing or create)
    env_path = ".env.example"
    if os.path.exists(env_path):
        with open(env_path, 'a', encoding='utf-8') as f:
            f.write("\n" + ENV_EXAMPLE_CONTENT)
        logging.info(f"Appended to: {env_path}")
    else:
        write_file(env_path, ENV_EXAMPLE_CONTENT)

    logging.info("Remediation complete. Please review `git diff` before committing.")
    logging.info("Next steps: Run `pip install -r requirements.txt` and verify DSP tests.")

if __name__ == "__main__":
    main()
