---
title: "M0 Placeholder Audio Provenance"
created_date: 2026-11-23
update_date: 2026-11-23
status: APPROVED
tags: [m0, audio, asset-provenance, fixtures]
---

# M0 placeholder audio provenance

These four short mono PCM WAV files were generated for this repository with
simple mathematical tones. No recordings, third-party assets, reference-game
sounds, middleware, or runtime procedural synthesizer are used.

| File | Original construction | Sandbox use |
| --- | --- | --- |
| [ambience.wav](ambience.wav) | 0.40 s blend of 50, 80, and 130 Hz tones | Low drone microphone bed |
| [motor.wav](motor.wav) | 0.25 s fundamental and harmonics at 112, 224, and 336 Hz | Actual translation or in-place turning |
| [strain.wav](strain.wav) | 0.20 s low dual tone with a small amplitude modulation | A requested physical drive step meets an obstruction |
| [collision.wav](collision.wav) | 0.24 s decaying tone and seeded noise | First contact in a continuous physical collision; no new damage |

All four are 12 kHz signed 16-bit PCM. The first three loop and the impact
is a one-shot. These are original provisional project assets, not hardware
signatures or a production mix. The scene has no real microphone permission
or external recording. [Launch and verify](../../README.md#verification).
