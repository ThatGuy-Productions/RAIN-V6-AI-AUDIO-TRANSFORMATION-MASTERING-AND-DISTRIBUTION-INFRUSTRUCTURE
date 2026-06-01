# Vocal Production Features — Pitch Correction & Instrument Synthesis

**Document ref:** RAIN-VOCAL-FEATURES-v1.0 · RAIN-MASTER-SPEC-v6.1

**Status:** FEATURE SPECIFICATION — Post-v6.0 Roadmap (Q3–Q4 2026)

---

## Overview

RAIN v6.1 introduces two production-critical capabilities for mid-tier creators:

1. **Vocal Pitch Correction** — Automatic vocal tuning with vibrato preservation, available to Creator+ tiers
2. **Instrument Synthesis** — AI-generated orchestration and instrumental arrangement, available to Artist+ tiers

Both features integrate seamlessly with the existing 12-stem separation pipeline and mastering engine.

---

## Part 1: Vocal Pitch Correction

### Architecture

**Core Dependencies:**
- `crepe` (CREPE v0.0.13 pitch detection, minimal overhead)
- `pyworld` (WORLD vocoder, deterministic pitch/formant separation)
- `librosa` 2.0+ (phase vocoder, time-stretching fallback)
- `pyrubberband` (optional GPU acceleration via Rubber Band library)

**Processing Stages:**
1. Load vocal stem (S3 key)
2. Extract F0 contour + confidence via CREPE
3. Detect musical key from F0 distribution
4. Generate correction curve (mode-dependent)
5. Apply WORLD-based pitch shift with optional formant preservation
6. Validate output quality
7. Export corrected vocal + pitch map metadata

### Data Model

```sql
CREATE TABLE pitch_correction_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Input analysis
    vocal_stem_key TEXT NOT NULL,
    vocal_analysis JSONB,  -- {f0_contour, vibrato, formants, confidence}
    
    -- User parameters
    target_key TEXT,                 -- "auto" | "C4" | "F#3" etc.
    correction_mode TEXT,            -- "snap" | "smooth" | "transparent"
    vibrato_preserve BOOLEAN DEFAULT true,
    formant_correction BOOLEAN DEFAULT false,
    blend_factor NUMERIC(3, 2) DEFAULT 1.0,  -- 0=no correction, 1=full
    
    -- Output
    corrected_vocal_key TEXT,
    pitch_map JSONB,                 -- {time_ms: target_cents}
    metrics JSONB,                   -- {f0_stddev_pre, f0_stddev_post, cents_shifted}
    
    status TEXT CHECK (status IN ('pending','processing','completed','failed')),
    error_code TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

ALTER TABLE pitch_correction_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY pitch_correction_isolation ON pitch_correction_sessions
  USING (user_id = current_setting('app.user_id')::UUID);
```

### Correction Modes

| Mode | Behavior | Use case |
|---|---|---|
| **snap** | Quantize to nearest semitone + transpose to target key | Pop, commercial vocals |
| **smooth** | Blend 50% correction with original contour | Natural, expressive vocals |
| **transparent** | Minimal correction, only fix gross errors | Jazz, classical soloists |

### API Endpoints

```
POST   /api/v1/pitch-correction/correct
  Query params:
    session_id: UUID (parent mastering session)
    target_key: "auto" | "C4" | "F#3" | ...
    mode: "snap" | "smooth" | "transparent"
    vibrato_preserve: boolean
    formant_correction: boolean (Creator+ only)
  Response: {
    correction_session_id: UUID,
    status: "processing" | "completed",
    output_vocal_key: "s3://...",
    pitch_map: {...},
    metrics: {...}
  }

GET    /api/v1/pitch-correction/{correction_id}/status
  Response: {
    status: "pending" | "processing" | "completed" | "failed",
    progress: 0–100,
    error_code?: RAIN-E*
  }
```

### Tier Gating

| Tier | Access | Quota | Max Duration |
|---|---|---|---|
| Free | ✗ | — | — |
| Spark | ✗ | — | — |
| Creator | ✅ Basic | 20/month | 5 minutes |
| Artist | ✅ Full | 50/month | 10 minutes |
| Studio Pro | ✅ Full | 100/month | 30 minutes |
| Enterprise | ✅ Full + formant | Unlimited | Unlimited |

### Error Codes

| Code | Meaning |
|---|---|
| RAIN-E710 | Vocal stem not found or unreadable |
| RAIN-E711 | CREPE model unavailable |
| RAIN-E712 | Pitch detection confidence too low (unvoiced audio) |
| RAIN-E713 | Key detection failed (insufficient harmonic content) |
| RAIN-E714 | WORLD vocoder synthesis failed |
| RAIN-E715 | Output validation failed (artifacts detected) |

---

## Part 2: Instrument Synthesis & Arrangement

### Architecture

**Core Dependencies:**
- Suno v3 API (REST, text-to-music generation)
- BS-RoFormer (stem separation, for breaking down generated mix)
- `librosa` (time-stretching, pitch-shifting for alignment)
- `pyloudnorm` (loudness matching)

**Processing Stages:**
1. Analyze original mix (key, tempo, spectral balance)
2. Generate synthetic instruments via Suno API (text-to-music)
3. Align generated stems to session key/tempo
4. Blend with original mix at user-specified ratio
5. Export individual stems + final combined mix

### Data Model

```sql
CREATE TABLE instrument_synthesis_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Input
    original_mix_key TEXT NOT NULL,
    stems_available TEXT[] NOT NULL,  -- ["vocals", "drums", "bass", ...]
    
    -- User parameters
    prompt TEXT NOT NULL,              -- Natural language description
    instrument_types TEXT[] NOT NULL,  -- ["strings", "brass", "pads", "sfx"]
    key_detected TEXT,                 -- "C major" | "auto"
    tempo_bpm NUMERIC(6, 2),
    style_reference TEXT,              -- "cinematic" | "lo-fi" | "ambient" | "orchestral"
    blend_factor NUMERIC(3, 2) DEFAULT 0.5,  -- 0–1
    num_variations INT DEFAULT 1,      -- 1–3 options
    
    -- Output
    synthesized_stems JSONB,           -- {instrument: s3_key}
    final_mix_key TEXT,
    generation_model TEXT,             -- "suno-v3"
    
    status TEXT CHECK (status IN ('pending','generating','mixing','completed','failed')),
    error_code TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

ALTER TABLE instrument_synthesis_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY instrument_synthesis_isolation ON instrument_synthesis_jobs
  USING (user_id = current_setting('app.user_id')::UUID);
```

### API Endpoints

```
POST   /api/v1/instruments/add
  Query params:
    session_id: UUID
    prompt: string (e.g. "Add orchestral strings, lush pads, vinyl crackle")
    instruments: string[] (e.g. ["strings", "pads", "sfx"])
    key: string (optional, auto-detected if omitted)
    tempo: number (optional, auto-detected if omitted)
    style: "cinematic" | "lo-fi" | "ambient" | "orchestral"
    blend_factor: 0.0–1.0
    num_variations: 1–3
  Response: {
    job_id: UUID,
    status: "generating",
    estimated_time_sec: 45
  }

GET    /api/v1/instruments/jobs/{job_id}
  Response: {
    status: "generating" | "mixing" | "completed" | "failed",
    progress: 0–100,
    synthesized_stems?: {instrument: s3_key},
    final_mix_key?: s3_url,
    error_code?: RAIN-E*
  }

GET    /api/v1/instruments/jobs/{job_id}/variations
  Response: [
    { variation_id: "v1", preview_url: "s3://..." },
    { variation_id: "v2", preview_url: "s3://..." },
    { variation_id: "v3", preview_url: "s3://..." }
  ]

POST   /api/v1/instruments/jobs/{job_id}/select-variation
  Body: { variation_id: "v1" }
  Response: { final_mix_key: s3_url }
```

### Tier Gating

| Tier | Access | Quota | Variations |
|---|---|---|---|
| Free | ✗ | — | — |
| Spark | ✗ | — | — |
| Creator | ✗ | — | — |
| Artist | ✅ | 10/month | 1 |
| Studio Pro | ✅ | 30/month | 3 |
| Enterprise | ✅ | Unlimited | 3 |

### Error Codes

| Code | Meaning |
|---|---|
| RAIN-E720 | Suno API unavailable or rate-limited |
| RAIN-E721 | Generation timeout (>5 minutes) |
| RAIN-E722 | Key/tempo detection failed on original mix |
| RAIN-E723 | Alignment (time-stretch / pitch-shift) failed |
| RAIN-E724 | Blending failed (loudness mismatch) |
| RAIN-E725 | S3 export failed |

---

## Part 3: Integration with Mastering Pipeline

### Enhanced Session Workflow

```
EXISTING STAGES 1–10: Core mastering
         ↓
[NEW] Stage 11a: OPTIONAL Pitch Correction
    - If user selects "Correct vocals"
    - Route to pitch_correction service
    - Re-blend corrected vocal into mix
         ↓
[NEW] Stage 11b: OPTIONAL Instrument Synthesis
    - If user selects "Add instruments"
    - Route to instrument_synthesis service
    - Blend synthesized stems with session
         ↓
EXISTING STAGES 12–13: Compliance + Distribution
```

### Session Model Extension

```sql
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS (
    pitch_correction_session_id UUID REFERENCES pitch_correction_sessions(id),
    pitch_correction_applied_at TIMESTAMPTZ,
    pitch_correction_metrics JSONB,
    
    instrument_synthesis_job_id UUID REFERENCES instrument_synthesis_jobs(id),
    instrument_synthesis_applied_at TIMESTAMPTZ,
    instruments_added TEXT[],
    
    ai_production_disclosures JSONB  -- {pitch_corrected: bool, instruments: [names]}
);
```

### AI Disclosure

Every session with pitch correction or synthesis triggers automatic population of:
- `ai_production_disclosures` (session metadata)
- C2PA AI disclosure fields (`digitalSourceType`, `actions`)
- DDEX AI disclosure (`ai_involvement_description`, per-component flags)

---

## Part 4: Implementation Roadmap

### Phase 1: Vocal Pitch Correction (Q3 2026, 4 weeks)

- [ ] Integrate CREPE + WORLD vocoder services
- [ ] Implement 3-mode correction engine
- [ ] Database migrations + API endpoints
- [ ] Tier gating (Creator+) + quota enforcement
- [ ] Error handling + validation
- [ ] Unit tests + integration tests
- [ ] UI preview (before/after waveforms)

### Phase 2: Instrument Synthesis (Q4 2026, 6 weeks)

- [ ] Suno v3 API integration
- [ ] Composition prompt generation logic
- [ ] Key/tempo detection + alignment
- [ ] Blending + loudness matching
- [ ] Variation selection UI
- [ ] Tier gating (Artist+)
- [ ] Error handling
- [ ] End-to-end tests

### Phase 3: Advanced Features (Q1 2027, ongoing)

- [ ] Reference-based instrument matching
- [ ] Custom LoRA fine-tuning (Enterprise)
- [ ] Voice cloning (Suno v4)
- [ ] Live stem preview (WebSocket)

---

## Part 5: Compliance & Provenance

### C2PA Manifest Updates

All pitch-corrected and instrument-synthesized outputs include:

```json
{
  "ai_assertions": [
    {
      "component": "pitch_correction",
      "model": "crepe-v0.0.13",
      "description": "Vocal pitch detection and correction via CREPE + WORLD vocoder",
      "applied": true,
      "confidence": 0.92
    },
    {
      "component": "instrument_synthesis",
      "model": "suno-v3",
      "description": "AI-generated orchestral strings, pads, synthesizers",
      "applied": true,
      "confidence": 0.87
    }
  ]
}
```

### DDEX ERN 4.3 AI Disclosure

```xml
<ai_involvement>
  <ai_involvement_type>processing</ai_involvement_type>
  <ai_components>
    <component>
      <component_type>pitch_correction</component_type>
      <model_name>CREPE v0.0.13 + WORLD Vocoder</model_name>
      <transparency_confidence>0.92</transparency_confidence>
    </component>
    <component>
      <component_type>instrumentation</component_type>
      <model_name>Suno v3</model_name>
      <transparency_confidence>0.87</transparency_confidence>
    </component>
  </ai_components>
</ai_involvement>
```

---

## Part 6: Cost & Performance

### Vocal Pitch Correction

- **Latency**: ~5–15 seconds per minute of audio (CPU-bound)
- **Cost**: <$0.01 per correction (local computation, no cloud GPU)
- **Quota**: Hard quota per tier (prevents abuse)

### Instrument Synthesis

- **Latency**: ~45–120 seconds per generation (Suno API call)
- **Cost**: $0.50–1.50 per generation (Suno API pricing)
- **Variations**: Up to 3 options per generation job

---

## Part 7: Testing Protocol

### Pitch Correction Tests

- [ ] CREPE F0 extraction matches reference signal (±2% error)
- [ ] Vibrato detection and preservation (manual listening validation)
- [ ] Key detection accuracy (>85% on commercial recordings)
- [ ] Formant shift correctness (spectral comparison)
- [ ] Output determinism (bit-identical across runs)

### Instrument Synthesis Tests

- [ ] Suno API integration (sandbox mode)
- [ ] Key/tempo alignment (±1 BPM, ±1 semitone tolerance)
- [ ] Blending loudness matching (±0.5 LU)
- [ ] Variation selection workflow
- [ ] Error recovery (API timeouts, rate limits)

---

## Part 8: Database Migrations

```python
# backend/migrations/versions/0006_vocal_instruments.py
"""Add pitch correction and instrument synthesis.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

def upgrade():
    # Pitch correction table
    op.create_table(
        'pitch_correction_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('parent_session_id', UUID(as_uuid=True), sa.ForeignKey('sessions.id', ondelete='CASCADE')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('vocal_stem_key', sa.String),
        sa.Column('vocal_analysis', JSONB),
        sa.Column('target_key', sa.String),
        sa.Column('correction_mode', sa.String),
        sa.Column('vibrato_preserve', sa.Boolean, default=True),
        sa.Column('formant_correction', sa.Boolean, default=False),
        sa.Column('blend_factor', sa.Numeric(3, 2), default=1.0),
        sa.Column('corrected_vocal_key', sa.String),
        sa.Column('pitch_map', JSONB),
        sa.Column('metrics', JSONB),
        sa.Column('status', sa.String),
        sa.Column('error_code', sa.String),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
    )
    op.execute("ALTER TABLE pitch_correction_sessions ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY pitch_correction_isolation ON pitch_correction_sessions "
        "USING (user_id = current_setting('app.user_id')::UUID)"
    )
    op.create_index('idx_pitch_correction_parent', 'pitch_correction_sessions', ['parent_session_id'])
    op.create_index('idx_pitch_correction_user', 'pitch_correction_sessions', ['user_id'])

    # Instrument synthesis table
    op.create_table(
        'instrument_synthesis_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('parent_session_id', UUID(as_uuid=True), sa.ForeignKey('sessions.id', ondelete='CASCADE')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('original_mix_key', sa.String, nullable=False),
        sa.Column('stems_available', sa.ARRAY(sa.String)),
        sa.Column('prompt', sa.Text, nullable=False),
        sa.Column('instrument_types', sa.ARRAY(sa.String), nullable=False),
        sa.Column('key_detected', sa.String),
        sa.Column('tempo_bpm', sa.Numeric(6, 2)),
        sa.Column('style_reference', sa.String),
        sa.Column('blend_factor', sa.Numeric(3, 2), default=0.5),
        sa.Column('num_variations', sa.Integer, default=1),
        sa.Column('synthesized_stems', JSONB),
        sa.Column('final_mix_key', sa.String),
        sa.Column('generation_model', sa.String),
        sa.Column('status', sa.String),
        sa.Column('error_code', sa.String),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
    )
    op.execute("ALTER TABLE instrument_synthesis_jobs ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY instrument_synthesis_isolation ON instrument_synthesis_jobs "
        "USING (user_id = current_setting('app.user_id')::UUID)"
    )
    op.create_index('idx_instrument_synthesis_parent', 'instrument_synthesis_jobs', ['parent_session_id'])
    op.create_index('idx_instrument_synthesis_user', 'instrument_synthesis_jobs', ['user_id'])

    # Session columns
    op.add_column('sessions', sa.Column('pitch_correction_session_id', UUID(as_uuid=True), sa.ForeignKey('pitch_correction_sessions.id')))
    op.add_column('sessions', sa.Column('pitch_correction_applied_at', sa.DateTime(timezone=True)))
    op.add_column('sessions', sa.Column('instrument_synthesis_job_id', UUID(as_uuid=True), sa.ForeignKey('instrument_synthesis_jobs.id')))
    op.add_column('sessions', sa.Column('instrument_synthesis_applied_at', sa.DateTime(timezone=True)))
    op.add_column('sessions', sa.Column('instruments_added', sa.ARRAY(sa.String)))
    op.add_column('sessions', sa.Column('ai_production_disclosures', JSONB))

def downgrade():
    op.drop_table('instrument_synthesis_jobs')
    op.drop_table('pitch_correction_sessions')
    op.drop_column('sessions', 'pitch_correction_session_id')
    op.drop_column('sessions', 'pitch_correction_applied_at')
    op.drop_column('sessions', 'instrument_synthesis_job_id')
    op.drop_column('sessions', 'instrument_synthesis_applied_at')
    op.drop_column('sessions', 'instruments_added')
    op.drop_column('sessions', 'ai_production_disclosures')
```

---

*See [[Architecture]] for the system overview. See [[Tiers-and-Pricing]] for access control. See [[Provenance-and-RAIN-CERT]] for C2PA integration.*
