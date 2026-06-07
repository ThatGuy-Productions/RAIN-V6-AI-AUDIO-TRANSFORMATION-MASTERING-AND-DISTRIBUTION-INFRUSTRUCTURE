# RAIN-V6 (R∞N): The Master Dossier
**Version:** 6.3.0 (Consolidated Release)  
**Architect:** Phil Bölke  
**Core Directive:** The Sovereign Artist Philosophy

---

## 1. What It Is: The Philosophy & Purpose

**RAIN-V6 is a complete post-recording and creation platform.** It functions as an end-to-end **Audio Transformation, Mastering, Trust, Security, and Distribution Infrastructure**, engineered specifically to reverse the modern music industry's trajectory toward centralized, cloud-dependent processing. It is built fundamentally on the **"Artist-First"** mandate.

In the current market, automated mastering tools subject an artist’s intellectual property to privacy risks (uploading unreleased stems to corporate clouds) and "clinical loudness"—a sonically flat result of aggressive amplitude maximization that destroys emotional nuance. RAIN serves as a technical correction to this paradigm.

Drawing inspiration from Phil Bölke’s creative background (e.g., *"SKRYWER"*, *"Hoe groet jy iemand wat nog hier is, maar nie meer hier is nie?"*), RAIN explicitly rejects the industry's obsession with "crushing" integrity out of audio for the sake of sheer volume. It prioritizes **artistic sovereignty** by ensuring that high-fidelity audio transformation occurs entirely within the artist’s local domain whenever possible, keeping IP safe and sonics intact.

---

## 2. What It Does: Core Capabilities

RAIN functions as a world-class, automated mastering engineer, a forensic provenance tracker, and an immersive audio renderer, all wrapped in a singular platform.

### A. The 16-Stage DSP Architecture
RAIN-V6 operates on a holistic 16-stage pipeline that unifies machine learning, cryptographic trust, and mastering-grade DSP:

1. **Format Normalization:** Resampling to internal 64-bit/48kHz space.
2. **Provenance Record:** Hashing incoming files and preparing C2PA manifest.
3. **Feature Extraction:** 43-dimensional analysis (Loudness, Dynamics, Spectral, Stereo, Transient, Tonal).
4. **AI Inference (RainNet v2):** Decoding processing parameters (46 neurons).
5. **Reference Matching:** Spectral/dynamic alignment with reference targets.
6. **Spectral Repair:** Deep-learning denoising/de-clipping.
7. **Source Separation:** 6-to-12 stem splitting (BS-RoFormer / LarsNet).
8. **Per-Stem Repair:** Artifact reduction on isolated stems.
9. **Per-Stem Processing:** Stem-Aware Intelligent Limiting (SAIL) and individual EQ.
10. **Master Bus Processing:** Global EQ, Multiband Compression, Stereo Widening.
11. **Loudness Targeting:** True-Peak look-ahead limiting.
12. **Spatial Rendering:** Stage 12 immersive (Atmos/binaural) encoding.
13. **QC Validation:** 18-point automated compliance checks.
14. **Forensics Watermark:** AudioSeal embedding and cryptographic signing.
15. **Output Packaging:** Format encoding (WAV/MP3/DDP) and metadata injection.
16. **Distribution:** Enterprise delivery routing to streaming endpoints.

### B. AI-Driven Decision Making (RainNet v2)
- **The Brain:** Operates on the 431KB RainNet v2 ONNX model (trained over 25 epochs, val_mae=0.41), which takes Mel-spectrograms and artist latent vectors and decodes them into 46 distinct parameters (neurons).
- **Proactive AI Co-Master Engineer:** Features an Intent Engine, Restraint System, and RAIN Score v2. It doesn't just apply processing; it diagnoses audio health and provides conversational, pull-based (confidence-driven) feedback to the artist.
- **Deterministic Heuristic Fallback:** If the neural net is deactivated, RAIN relies on an acoustically perfected, deterministic algorithmic fallback based on genre and platform rules. 

### C. Forensic IP Protection & Provenance
- **EU AI Act (Article 50) Compliance:** Fully compliant with upcoming global regulations.
- **C2PA Manifest Generation:** Uses real Ed25519 cryptography to sign Audio Definition Models, ensuring a transparent chain of custody from creator to listener.
- **AudioSeal Watermarking:** Embeds imperceptible cryptographic watermarks directly into the audio buffer to prevent AI scraping and intellectual property theft.

### D. Immersive Delivery
- **Stage 12 Spatial Audio:** Native encoding for Dolby Atmos and spatial formats, supporting binaural down-mixes and interleaved multi-channel deliverables.
- **Multi-Format Export:** Generates 24-bit/48kHz WAVs, 320kbps MP3s (with TPDF dither and LUFS correction), DDP images for CD manufacturing, and Spatial ADM BWF files.

---

## 3. How It Does It: Technical Architecture

RAIN-V6 is built on a highly parallelized, hybrid technology stack optimized for both local execution and enterprise scaling.

### Frontend: The "Roon Crystal" UI
- **Stack:** React 19, Vite 7, Tailwind 4, Radix UI, Framer Motion.
- **Aesthetic:** A glassy, 3D, professional visual identity (teal/emerald DNA) that completely abandons "max-width" constraints for an edge-to-edge workspace.
- **Features:** Voice command hooks, resizable panels, tabbed routing (Mastering, AI Assist, Spatial, Albums, Distribution). 

### Backend: FastAPI & Python Orchestration
- **API Engine:** FastAPI executing secure, auth-gated asynchronous routing.
- **Database & State:** PostgreSQL 18 for persistence, Valkey 9.0 (Redis fork) for high-speed caching and rate limiting (SlowAPI).
- **Security:** Hardened API dependencies, sequential UUIDv7 implementation, and strict Tier Enum access controls (Free/Pro/Enterprise). Free tier strictly enforces the local-first mandate—unreleased audio never touches Amazon S3.

### DSP Engine: RainDSP (C++ Native / WASM)
- **The Bottleneck Eradicated:** Older versions used slow Python loops (70M iterations per 5-min track). RAIN-V6 integrates `RainDSP`, a custom C++20 engine that processes audio near-instantly.
- **Dual Path Execution:** Compiled to native machine code for the backend rendering environment, and WebAssembly (WASM) for zero-latency, local-first browser monitoring.

### Deep Source Separation (ML Workers)
- **GPU Inference:** Uses `Celery` workers to orchestrate VRAM-heavy tasks.
- **BS-RoFormer SW:** Replaced the legacy Demucs model for incredibly accurate 6-stem separation.
- **LarsNet Integration:** Utilizes deep-drum demixing for Pass 3 separation, perfectly splitting the drum bus into Kick, Snare, and Hats instead of relying on rudimentary frequency band-splitting.

---

## 4. The Horizon: Next Evolutions

RAIN is not static. The architecture is pointing toward the following massive structural leaps:

### 1. Decentralized Compute (Local AI Swarm)
Moving completely away from any reliance on centralized cloud APIs. The objective is to allow artists to run local Large Language Models (LLMs) and ML models (like LarsNet and RainNet) directly on their consumer hardware (Apple Silicon / RTX GPUs), making the entire studio completely self-contained and sovereign.

### 2. Personalized LoRA Customization (Enterprise)
The infrastructure is currently laying the groundwork for HuggingFace PEFT LoRA training stubs. This evolution will allow high-end studio facilities or record labels to train their own microscopic LoRA weights on top of the RAIN base model. Instead of a generic master, the AI will learn the exact sonic thumbprint and preferences of a specific engineer or artist.

### 3. Generative Intent Mapping (Vocal Production v6.1)
Extending the AI Co-Master concept into multitrack vocal production. Future capabilities will introduce deep perceptual alignment for lead vocals—evaluating sibilance, tuning stability, and dynamic presence against the instrumental stem, then suggesting micro-automation rather than static compression. 

### 4. Dynamic Interactive Spatial Panning
Evolving the static Stage 12 Spatial Audio renderer into an interactive 3D soundfield. Artists will use the Roon Crystal UI to visually position stems in a 360-degree holographic space, with RAIN automatically calculating the acoustic reflections and binaural transfer functions (HRTFs) in real-time before export.

---
*End of Dossier.*
