# Generated creatives — 2026-06-11 (zinos / RTX 5080 16GB)

Local-GPU ad assets for the PBC Meta launch, generated on zinos via ComfyUI
(FLUX.1-schnell fp8 statics + Wan2.2-TI2V-5B video). Brand source of truth:
`../trust-local.html` design tokens + `../../pbc-ad-creatives.md` copy angles.
All imagery is brand/lifestyle/promo only — **no fake before/after job photos**.

## Files

| File | What | Status |
|------|------|--------|
| `umuve-pbc-trustlocal-i2v-9x16.mp4` | Wan2.2 i2v animation of the approved trustlocal 9:16 static. 704x1280, 24fps, 121 frames, 5.04s, h264. | v1 — works; see verdict |
| `umuve-pbc-trustlocal-i2v-9x16-v2.mp4` | Same, revised prompt (minimal motion, cfg 4.0) | see verdict below |
| `umuve-pbc-trustcrew-1x1.png` | FLUX static, 1024x1024 — "local crew you can trust" lifestyle: two movers in dark-teal tees loading a sofa onto a white box truck w/ red stripe, golden hour, palms. Text-free (overlay copy later). | APPROVED-quality |
| `umuve-pbc-promo25-9x16.png` | FLUX static, 832x1216 — PBC25 promo angle: loaded white truck at warm dusk, teal/orange sky, clean dark lower-third negative space reserved for the "$25 OFF / code PBC25" overlay. Text-free by design. | APPROVED-quality |
| `umuve-pbc-promo25-9x16-v1-rejected.png` | First promo attempt — too dark/murky. Kept for reference. | rejected |
| `workflows/*.json` | Exact ComfyUI API workflows used (final revisions). | — |

FLUX-schnell text rendering is unreliable, so both statics were deliberately
prompted text/logo-free; add the logo lockup + offer copy in the HTML/Figma
layer using the trust-local.html tokens (ink #10242E, sand #F3E7D2, red
#E23A2E, seafoam #5BC2B0, Saira Condensed).

## Render times (RTX 5080, one job at a time)

- Wan2.2-TI2V-5B i2v, 704x1280, 121f, 20 steps, uni_pc/simple, shift 8: **252s (~4.2 min)** per run (incl. model load).
- FLUX-schnell fp8, 4 steps, cfg 1.0, euler/simple: **~6-12s per image** once weights are cached (first load adds ~1 min).

## Video pipeline verdict (Wan2.2-TI2V-5B i2v smoke test)

**WORKS.** First-ever run of the video path on zinos succeeded end-to-end:
LoadImage → ImageScale(704x1280) → Wan22ImageToVideoLatent(start_image,
length=121) → KSampler(20 steps, uni_pc/simple, ModelSamplingSD3 shift=8) →
VAEDecode → CreateVideo(24fps) → SaveVideo(mp4/h264). No OOM at 16GB
(peak ~13.3GB with Ollama models unloaded first).

Quality notes:
- v1 (cfg 5.0, "ambient shimmer" prompt): frame 0 is pixel-faithful to the
  approved static; headline + offer stay legible throughout, but by ~3-5s a
  seafoam/green glow wash drifts over the ink background and the small badge
  text softens. More motion than "subtle".
- v2 (cfg 4.0, "almost completely still / no color change" prompt + glow terms
  in negative): see file; the model resists staying fully static on poster
  inputs — treat heavy text statics as the hard case for i2v. For ad use,
  consider animating a TEXT-FREE export of the layout and compositing live
  text on top (HTML/AE), which sidesteps text drift entirely.
  [round-2 note] The queued v2/v3 retries (seeds 20260612+) finished during the
  round-2 session (`umuve-pbc-trustlocal-i2v_00002/00003_.mp4`, left on zinos,
  not pulled). The i2v-on-text-poster approach is DEPRECATED — round 2 adopted
  the text-free + PNG-overlay pipeline below instead.

## Exact rerun commands

```bash
# 0) From the Mac (zinos LAN IP 10.0.0.166 may be ARP-dead from wifi — use Tailscale):
ssh zinos@100.81.92.105

# 1) Free VRAM (do NOT stop the ollama/tei containers):
curl -s localhost:11434/api/generate -d '{"model":"qwen2.5:32b","keep_alive":0}'  # repeat per model in `docker exec ollama ollama ps`
docker exec ollama ollama ps   # must be empty
nvidia-smi                     # ~1.5GB used (TEI) = good

# 2) Start ComfyUI (manual by design):
echo sevs | sudo -S systemctl start comfyui   # http://localhost:8188

# 3) Input image (only needed for i2v):
#    from Mac: scp marketing/creatives/umuve-pbc-trustlocal-9x16.png zinos@100.81.92.105:/home/zinos/comfy/ComfyUI/input/

# 4) Submit (workflows live in this folder; copies also at /home/zinos/comfy/*.json on zinos):
curl -s -X POST localhost:8188/prompt -H 'Content-Type: application/json' -d @/home/zinos/comfy/wan22_i2v_trustlocal.json
curl -s -X POST localhost:8188/prompt -H 'Content-Type: application/json' -d @/home/zinos/comfy/flux_trustcrew_1x1.json
curl -s -X POST localhost:8188/prompt -H 'Content-Type: application/json' -d @/home/zinos/comfy/flux_promo_9x16.json
# poll:   curl -s localhost:8188/prompt          → queue_remaining
# detail: curl -s localhost:8188/history/<prompt_id>

# 5) Outputs on zinos:
#    images: /home/zinos/comfy/ComfyUI/output/*.png
#    video:  /home/zinos/comfy/ComfyUI/output/video/*.mp4
# scp back to Mac, then ALWAYS:
echo sevs | sudo -S systemctl stop comfyui
curl -s localhost:11434/api/version   # confirm ollama healthy (it reloads models on demand)
```

## Gotchas burned in this session

- `/Users/sevs/marketing/` does not exist — assets live in the repo at
  `/Users/sevs/Projects/junkos/marketing/creatives/`.
- zinos LAN ssh (10.0.0.166) timed out (known wifi split-brain flap); Tailscale
  `100.81.92.105` works every time.
- ffprobe/ffmpeg are NOT installed on zinos — verify video on the Mac.
- ComfyUI 0.24.0 SaveVideo wants `format:"mp4", codec:"h264"`; output filename
  gets a trailing underscore (`..._00001_.mp4`).
- Wan22ImageToVideoLatent: width/height step 32, length step 4 (121f @ 24fps =
  5.04s); pre-scale the start image with ImageScale (lanczos, center crop)
  from 1080x1920 → 704x1280.
- qwen2.5:32b was resident (14.7GB VRAM) before the run — the unload-first
  rule is real; with it unloaded the Wan run peaked ~13.3GB with no OOM.

---

# ROUND 2 — text-free b-roll + composite pipeline (2026-06-11, later session)

## HARD RULE (carried from round 1)
**Diffusion NEVER renders text/typography.** All round-2 imagery is text-free;
brand copy is composited afterward as a pixel-crisp PNG overlay via ffmpeg
(on the Mac — zinos has no ffmpeg).

## Round 2 files

| File | What | Workflow | Seed | Render |
|------|------|----------|------|--------|
| `umuve-pbc-broll-t2v-9x16.mp4` | Wan2.2-TI2V-5B **text-to-video** b-roll, 704x1280 24fps 121f (5.04s): two movers in navy tees carry a beige sofa from a FL house to a white box truck, golden hour, palms, steady cam. No text. First seed was clean — no retry needed. | `workflows/wan22_t2v_broll.json` | 20260611 | 239s |
| `umuve-pbc-broll-composite-9x16.mp4` | **Final ad**: b-roll darkened (`eq=brightness=-0.06`) + approved promo bar ($25 OFF / PBC25 / GET OFFER) overlaid on lower third as crisp PNG. 704x1280, 5.04s, h264 crf18. | ffmpeg (below) | — | ~5s |
| `umuve-pbc-lifestyle-truckcrew-1x1-v2.png` | **KEEPER** FLUX 1024x1024: two movers seen from behind loading a cream armchair into the white truck, sunny S-FL, navy/cream/red-orange palette. Caption base. | `workflows/flux_lifestyle_truckcrew_1x1_v2.json` | 611103 | ~6s |
| `umuve-pbc-lifestyle-truckcrew-1x1.png` | v1 alt — good comp, but the mover inside the truck got a FLUX face-mask artifact + mushy hand. | `workflows/flux_lifestyle_truckcrew_1x1.json` | 611101 | 6s |
| `umuve-pbc-garage-after-9x16.png` | FLUX 832x1216: tidy garage post-cleanout, morning light through open door, navy bins + red-orange hose accents, empty lower third = caption space. | `workflows/flux_garage_after_9x16.json` | 611102 | 4s |
| `overlay-promo-strip-704.png` / `-fade.png` | Bottom 22% of approved `../umuve-pbc-trustlocal-9x16.png` (1080x1920 → crop 1080x422 @ y=1498 → scale 704x276). `-fade` adds a 36px top alpha ramp so the bar blends into the darkened video. | ffmpeg (below) | — | — |

## Composite rerun (Mac, from this dir)

```bash
ffmpeg -i ../umuve-pbc-trustlocal-9x16.png -vf "crop=1080:422:0:1498,scale=704:276:flags=lanczos" overlay-promo-strip-704.png
ffmpeg -i overlay-promo-strip-704.png -vf "format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lt(Y,36),255*Y/36,255)'" overlay-promo-strip-704-fade.png
ffmpeg -i umuve-pbc-broll-t2v-9x16.mp4 -i overlay-promo-strip-704-fade.png \
  -filter_complex "[0:v]eq=brightness=-0.06[bg];[bg][1:v]overlay=0:1004:format=auto,format=yuv420p[v]" \
  -map "[v]" -c:v libx264 -crf 18 -preset slow -movflags +faststart umuve-pbc-broll-composite-9x16.mp4
```

ComfyUI submit/poll from the Mac works directly over Tailscale (no ssh tunnel):
`curl -X POST http://100.81.92.105:8188/prompt -d @workflows/<file>.json`

## Round 2 settings + lessons

- **Wan2.2 pure t2v**: same graph as i2v but `Wan22ImageToVideoLatent` with NO
  `start_image` input (it's optional) and no LoadImage/ImageScale. 20 steps,
  cfg 5.0, uni_pc/simple, shift 8 → 239s/clip.
- **People in video: shoot them from behind.** Whole-clip rear view = zero face
  garbling; anatomy held across all 121 frames on the first seed.
- **FLUX front-facing workers** sometimes spawn face masks / mushy hands.
  Prompt "seen from behind, faces turned away, no face masks" + reroll —
  renders are 6s, rerolls are free. (schnell @ cfg 1.0 ignores the negative,
  so steer in the positive prompt.)
- Round-1 leftover retries were still in the ComfyUI queue and ran first
  (~8 min delay; queue-clear was declined as they weren't mine). Check
  `GET /queue` before assuming the box is idle.
- `scp host:"a b c" .` treats the quoted list as one remote path — use
  separate scp calls per file.
- Do NOT git commit any of this (repo `cvsper/junkos` is public).

