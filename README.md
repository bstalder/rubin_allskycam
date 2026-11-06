# rubin_allskycam — all-sky camera cloud reduction

Reduction of the Rubin Observatory all-sky camera (Canon 5D Mark IV + EF 8–15 mm fisheye, Cerro Pachón; "allskycam" below, to keep it distinct from LSSTCam) into a measured per-frame cloud, transparency and sky-brightness record, 2021-07 → present.

This repository is being **handed over to DM to operate automatically**. Until 2026-10-30 it ran by hand at USDF as `earlyoperations/system_performance/allsky/` in [bstalder/rubin_notebooks](https://github.com/bstalder/rubin_notebooks), and its git history is carried over. Its main consumer is the ROSP-11 time-loss analysis in [lsst/sp_notebooks `tracking_hub/ops/rosp-11_time_loss_accounting/`](https://github.com/lsst/sp_notebooks/tree/main/tracking_hub/ops/rosp-11_time_loss_accounting): `allsky_cloud_analysis.ipynb` (validation against the flag, LSSTCam zero points and DREAM, climatology, deep index §6.1) and `weather_downtime_analysis.ipynb`. The long-baseline weather-downtime fraction for the scheduler simulations is a record in rubin_notebooks `earlyoperations/system_performance/weather_downtime_climatology.ipynb`.

Contact: Brian Stalder.

## Status at handover (2026-10-30)

* **Record:** 1,685 nights, 966,103 reduced dark frames, 2021-07-09 → 2026-10-29, reduced at USDF into `/sdf/data/rubin/user/stalder/allsky` (278 GB). Nights from 2026-10-30 on are not reduced.
* **Code:** pipeline v6 plus the deep index (pipe_version 6, deep v1). Every night is on v5 or v6, and v6 changed only the astrometry seeding and plate-scale scan.
* **Camera:** body 8323 + lens 0552 since 2026-10-10. It was refocused on 2026-10-16 (star FWHM 1.4 px, the best on record). The 8–15 mm zoom creeps between visits: plate scale 755 → 862 px/rad from 10-16 to 10-27. Focus holds, and v6 follows the creep.
* **Headline:** fraction of dark time with cloud index > 0.3 is **0.152** (equal-month mean, 2021–26; 0.129 at > 0.5). Validated against the Scheduler WEATHER flag: P(index > 0.3 | WEATHER) = 0.69, P(index > 0.3 | OPERATIONAL) = 0.05.
* **Regression check of this repository's layout change:** 24 frames of 2026-10-27 were reduced with the old rubin_notebooks code and with this repository's code, each into its own scratch root. `frames`, `catalogs`, `matches`, `streaks`, `maps`, the night solution, `deep_matches` and `deep_frames` are bit-identical. `build_frame_index.py` and `build_unit_history.py` reproduce the production index (same URIs for every common frame) and unit table.

## What the pipeline does

1. **Index** both raw archives (`build_frame_index.py`) and read the camera body/lens serials of every night from EXIF (`build_unit_history.py`). Three bodies and three lenses were swapped six times; see *Camera units* below.
2. **Reduce** each night (`allsky_reduce.py`), about 1.5 min a night at 48–60 workers. For every 30 s dark frame (sun < −12°), read the CR2 green plane and find stars (DAOStarFinder). Solve a tilt-aware fisheye astrometric model against the Yale BSC, refining the running solution and following the plate-scale creep. Then match BSC V < 6 stars, fit a zero point, and write HEALPix NSIDE-32 maps of catalog stars, detected stars and sky brightness, plus streaks and an 8×-binned image.
3. **Derive** (`finalize_rerun.sh`): re-gate astrometry from the stored detections (`regate_frames.py`), then build a clear-sky completeness model P(detect | V, alt, local sky) per service stint × month (`build_completeness.py`). The per-frame **cloud index** = 1 − observed/expected for V < 5.5 stars above 20°, per frame and per NSIDE-8 cell (`cloud_metric.py`). Finally write the summary tables (`build_index_tables.py`, `build_nightly.py`).
4. **Deep index** (`finalize_deep.sh`): Hipparcos V < 7.5 matched to the same detections with no CR2 re-read (`deep_match.py`), with its own completeness model (`build_completeness_deep.py`). It gives `cloud_idx_deep` and `ext_deep`, a grey extinction in magnitudes that is sensitive to thin cloud, plus NSIDE-8/16 cell maps (`cloud_metric_deep.py`, `build_deep_tables.py`). It runs alongside the standard index and does not replace it.

`follow_night.sh` runs steps 1–4 for one night in progress: it re-reduces hourly and finalizes at the end.

## Repository layout

| file | role | hand over? |
|---|---|---|
| `allsky_paths.py` | **site configuration**: product root, raw archives, S3 endpoint/profile/bucket, external cache dir; all overridable by environment | yes |
| `allsky_units.py` | camera service stints (`stint_keys`), manual refocus `BREAKS`, young-stint `PROXY` | yes (see issue 3) |
| `build_frame_index.py`, `build_unit_history.py` | archive index, camera body/lens per night | yes |
| `allsky_reduce.py` | per-frame reduction (the only step that reads CR2s) | yes |
| `regate_frames.py`, `build_completeness.py`, `cloud_metric.py`, `build_index_tables.py` | standard cloud index | yes |
| `deep_match.py`, `build_completeness_deep.py`, `cloud_metric_deep.py`, `build_deep_tables.py` | deep cloud index | yes |
| `finalize_rerun.sh`, `finalize_deep.sh`, `follow_night.sh`, `run_nights.sbatch` | drivers (manual, USDF Slurm) | replace with DM orchestration |
| `focus_check.py` | star FWHM in raw cutouts: detects refocus / defocus | yes (issue 3) |
| `build_nightly.py` | per-night join with ROSP-11 caches (Scheduler, EFD, almanac, nowcast, downtime attribution); writes `allsky_cloud_frames.parquet` for the downtime notebook | analysis side, decide (issue 6) |
| `build_dream_dense.py`, `sample_dream.py` | DREAM cloud maps from the LFA, joined to allskycam and LSSTCam | analysis side, decide (issue 6) |
| `fetch_night_demo.py`, `render_cam_dream.py` | side-by-side allskycam/DREAM frames and movies | optional (viz) |
| `rerun_notebooks.sh` | re-executes the two ROSP-11 notebooks | analysis side |

The scripts are flat modules that import each other (`from allsky_reduce import ...`), so run them from the repository root with `python3 -E` (not `-P`, which drops the script directory from `sys.path`). `pyproject.toml` lists the dependencies; the repository is not yet an installable package (issue 8).

## Configuration

All site paths are in `allsky_paths.py`, and each can be overridden by environment:

| variable | default (USDF) | used by |
|---|---|---|
| `ALLSKY_OUT` | `<repo>/data/allsky` (set it; the 2021–26 products are at `/sdf/data/rubin/user/stalder/allsky`) | everything |
| `ALLSKY_DISK_ARCHIVE` | `/sdf/data/rubin/offline/allsky/storage` (2021-07-10 → 2024-02-26) | `build_frame_index.py` |
| `ALLSKY_LFA_BUCKET`, `ALLSKY_LFA_PREFIX` | `rubinobs-lfa-cp`, `AllSkyCamera/` (2024-02-06 → present) | index, unit history, DREAM |
| `ALLSKY_S3_ENDPOINT`, `ALLSKY_S3_PROFILE` | `https://s3dfrgw.slac.stanford.edu/`, `lfa` | all S3 reads |
| `AWS_SHARED_CREDENTIALS_FILE` | `~/.lsst/aws-credentials.ini` | boto3 |
| `SYSTEM_PERFORMANCE_DATA_DIR` | `/sdf/data/rubin/user/stalder/system_performance_data` | `build_nightly.py`, `build_dream_dense.py` (required); `build_completeness.py` (optional) |
| `PYTHON` | `lsst-scipipe-13.0.0` interpreter in the shell drivers | drivers |

Dependencies (`pyproject.toml`): numpy, pandas, pyarrow, scipy, astropy, photutils, healpy, h5py, **rawpy** (CR2 decoding, LibRaw), **exifread**, boto3, opencv-python-headless; optionally matplotlib for the viz scripts. All are in `lsst-scipipe-13.0.0`.

## Running (today, by hand at USDF)

```bash
export ALLSKY_OUT=/sdf/data/rubin/user/stalder/allsky
export SYSTEM_PERFORMANCE_DATA_DIR=/sdf/data/rubin/user/stalder/system_performance_data
PY=/sdf/group/rubin/sw/conda/envs/lsst-scipipe-13.0.0/bin/python3
cd rubin_allskycam

# catch up nights NIGHT1 NIGHT2 ...
$PY -E build_frame_index.py                         # ~2 min, lists both archives
$PY -E build_unit_history.py 32                     # ~2 min, camera body/lens per night
$PY -E allsky_reduce.py NIGHT1 NIGHT2 --workers 48  # ~1.5 min/night; add --force to redo a night
echo NIGHT1 NIGHT2 | tr ' ' '\n' > $ALLSKY_OUT/index/nights_catchup_YYYYMMDD.txt
PYTHON=$PY ./finalize_rerun.sh $ALLSKY_OUT/index/nights_catchup_YYYYMMDD.txt   # ~25 min, every night
PYTHON=$PY ./finalize_deep.sh  $ALLSKY_OUT/index/nights_catchup_YYYYMMDD.txt   # ~25 min, every night

# or follow tonight, re-reducing hourly and finalizing at the end
./follow_night.sh 20261030 2026-10-31T12:15 3600

# batch re-reduction (Slurm, rubin:commissioning / milano), from the repository root
sbatch --array=0-5 run_nights.sbatch <night list>
sbatch --export=ALL,ALLSKY_EXTRA=--force --array=0-3 run_nights.sbatch <night list>
```

Inputs that must exist under `ALLSKY_OUT` before a first run (copy from the USDF root):
* `catalogs/bsc5_v50.parquet`: Yale Bright Star Catalogue 5th ed. (VizieR V/50), all 9,096 stars with positions. The reducer keeps V < 6 for matching, V < 4 for astrometry and V < 5.5 for the index.
* `catalogs/hipparcos_v85.parquet`: Hipparcos main catalog (VizieR I/239), the 61,293 stars with V < 8.5, positions at epoch J1991.25. `deep_match.py` derives `catalogs/hip_deep_v75.parquet` from it.
* `calib/astrometry_bootstrap_clear.json`: the fall-back astrometric seed. `calib/astrometry/<day_obs>.json` holds the per-night solutions (1,627 nights), which seed the nearest night of the same body + lens.
* For a fresh `ALLSKY_OUT` the whole history must be present, or rebuilt, before the completeness model is meaningful. The model pools every reduced night of a service stint.

## Issues to be decided for the handover

1. **Where it runs and who triggers it.** Today a person runs the driver scripts, or `follow_night.sh` under `nohup` on an interactive node; there is no cron at USDF for this account. Options: a scheduled job at USDF (Slurm cron, or a Kubernetes CronJob in DM's environment) running *index → reduce last night → finalize* each morning; or a Prompt-Processing-style trigger on new LFA objects. **DM to decide.** Each frame is independent, so the reduction maps well onto a per-night batch job.

2. **Product storage, format and ownership.** Products are parquet / HDF5 / JSON files under one user directory (278 GB; about 170 MB/night standard + 22 MB/night deep, about 70 GB/year). Decide: a DM-owned location; whether products stay files or go into the Butler, ConsDB or the EFD (the per-frame cloud index and the nightly summary are natural ConsDB/EFD tables); retention for the large intermediates (`catalogs/` 93 GB, `maps/` 86 GB, `matches/` 58 GB, `deep_matches/` 37 GB), which can be regenerated from the CR2s; and whether the 2021–26 record is migrated or re-reduced (re-reduction is about 1,700 nights × 1.5 min of 48-core time). The USDF copy can stay as the reference for validating DM's first runs.

3. **Camera service visits need a person today.** A refocus or zoom reset without a body/lens swap starts a new completeness "stint" only when someone adds the night to `allsky_units.BREAKS`. Until the new stint has 800 dark frames of its own, `allsky_units.PROXY` can borrow a matching stint's reference. Without the break the clear-sky reference mixes two focus states: on 2026-10-16 the 2.7-px reference would have read thin cloud as clear on the 1.4-px camera. Body/lens swaps are detected automatically from EXIF. Options: detect visits automatically from a step in star FWHM (`focus_check.py` already measures it) or in plate scale and disk radius (stored per frame); or keep a documented operator step with an alert. Either way someone in the observatory must report camera visits. The camera has no telemetry; the only signals are the EXIF tags and the images.

4. **Full-archive recompute on every update.** Both finalize scripts rebuild the completeness models from every night and recompute the cloud index for every night (about 50 min together today, and growing). This is correct, because adding nights changes the month/stint reference, but it is wasteful nightly. Options: score new nights against the current model each night, and rebuild the models weekly or after a camera visit (the change to old nights is ≤ 0.01 in index in practice); or make the model per stint-month immutable once the month closes. **Decide which values are "final"** and how the downstream tables are versioned.

5. **External dependency on ROSP-11 caches.** `build_completeness.py` reads `scheduler_observatory_status.parquet` only if it exists (diagnostic `oper` column; the clear-sky reference does not use it). `build_nightly.py` and `build_dream_dense.py` need several ROSP-11 caches: Scheduler status, almanac, ConsDB pointings, meteoblue nowcast, EFD aggregates and the downtime attribution. These are built by `build_log_cache.py` / `build_weather_cache.py` in rubin_notebooks. Decide whether DM takes these joins (by querying ConsDB/EFD directly), or the reduction stops at `index/cloud_all_frames.parquet` + `index/deep_nightly.parquet` and ROSP-11 keeps the joins.

6. **Analysis-side scripts.** `build_nightly.py`, `build_dream_dense.py`, `sample_dream.py`, `fetch_night_demo.py`, `render_cam_dream.py` and `rerun_notebooks.sh` serve the ROSP-11 analysis, not the reduction. Decide: keep them here as optional tools, or move them back to the analysis (sp_notebooks or rubin_notebooks). In either case **agree the interface**: which tables DM publishes, their schema, and where. The ROSP-11 notebooks read `index/allsky_nightly.parquet`, `index/cloud_all_frames.parquet`, `index/frames_all_regated.parquet`, `index/cloud_pix8_nightly.parquet`, `index/streaks_nightly.parquet`, `index/deep_cloud_all_frames.parquet`, `index/deep_nightly.parquet`, `calib/clear_sky_completeness_deep.parquet`, and `SYSTEM_PERFORMANCE_DATA_DIR/allsky_cloud_frames.parquet`.

7. **Credentials and data access.** S3 reads use a personal AWS shared-credentials profile `lfa` against the USDF gateway. DM needs a service identity with read access to `rubinobs-lfa-cp/AllSkyCamera/` (and `DREAM/` if issue 6 keeps DREAM) and to the pre-2024 disk archive. Reading at the summit or from another site only needs `ALLSKY_S3_ENDPOINT` / `ALLSKY_LFA_BUCKET` changed.

8. **Packaging and tests.** The scripts are flat modules run from the repository root; there are no unit tests. Suggested: turn them into a package (`rubin_allskycam/`) with command-line entry points; add a regression test that reduces a few fixed frames (clear, moonlit, cloudy, swap night) and compares against stored outputs; and add a test of `allsky_units.stint_keys`. Decide whether this lives in the Science Pipelines stack (EUPS, `lsst-scipipe`) or as a standalone pip-installable package. The dependencies `rawpy` (LibRaw) and `exifread` are not in the DM stack baseline everywhere.

9. **Monitoring and quality gates.** The manual checks today are: astrometry success and rms per night (`frames.ast_mode`, `ast_rms_px`; the ROSP-11 notebook gates nights with median rms > 1.4 px); a clear-sky index floor near 0 on clear nights (a flat 0.1–0.6 floor was the v1/v3 failure mode); plate-scale creep (`astrometry_p[:, 5]`); and star FWHM after any visit. These should become alerts. A night with no solved frames (overcast) is normal. A night where clear frames fail is not.

10. **Repository home and name.** This repository is currently `bstalder/rubin_allskycam` (personal). Decide the GitHub org (lsst, lsst-dm or lsst-sitcom) and name before DM forks it; licence and copyright are carried over from rubin_notebooks (GPL-3.0 / BSD-3-Clause dual licence).

11. **Camera hardware.** Not a DM issue, but it affects the record. The shutter on body 8323 has at least 792,547 archived actuations against a 150,000 rating, and the zoom ring creeps after each visit. A body swap or a zoom lock changes the stint structure (issue 3).

Known limitations of the measurement (relevant to whoever owns the data): the standard index sees thick cloud, not thin; the deep index measures thin cloud only on sharp stints (FWHM ≲ 1.5 px); stars within 25° of the moon are excluded; the 2021-07 → 2022-05 archive directories are UTC dates (handled by the per-frame `night` column); the streak counts are not validated against a satellite catalog.

---

# Reference: data, camera history and pipeline versions

### Data
| archive | span | location |
|---|---|---|
| disk | 2021-07-10 → 2024-02-26 | `/sdf/data/rubin/offline/allsky/storage/utYYMMDD/` |
| LFA | 2024-02-06 → present | `s3://rubinobs-lfa-cp/AllSkyCamera/YYYY/MM/DD/` via `https://s3dfrgw.slac.stanford.edu/`, profile `lfa` in `~/.lsst/aws-credentials.ini` |

One CR2 (+JPEG) per minute, ~850 frames per `day_obs` (seq 0001 at 12:00 UTC), 30 s ISO 400 f/4 at night.
**Use the CR2** (14-bit linear, sky ≈ 15–35 ADU above black 2049, noise ≈ 5 ADU); the JPEG sky is quantized to a few DN.
Focal length changed over time (EXIF): 8 mm (2021-07, 2022, 2026) / 9 mm (2021-10 → 2024-04) / 10 mm (2024-10 → 2025); the illuminated disk radius (1070–1300 px in the green plane) tracks it and the astrometric bootstrap rescales from it.

**Camera units.** Three Canon bodies and three lenses were swapped six times (`build_unit_history.py` reads the EXIF body/lens serials of every night → `index/unit_nights.parquet`, `index/unit_epochs.parquet`). Every swap happened in daytime. A unit is labelled `body/lens/focal` by the serials' last four digits, e.g. `8323/0552/10`. The camera writes no shutter count; archived frames per body are a lower bound on actuations.

Shutter actuations (archived frames, one CR2+JPEG pair = one shot) as of 2026-10-10 23:01 UTC (the epoch table below is updated to 2026-10-30). These are lower bounds: shots before 2021-07-10, test shots and archive gaps are not counted. Canon rates the 5D Mk IV shutter at 150,000 actuations.

| body (serial) | internal serial | epochs in service | archived actuations |
|---|---|---|---|
| B1 087231009118 | EK0899619 | 2021-07-10 → 2022-05-20, 2025-12-04 → 2026-07-18 | 433,915 |
| B2 086022008323 | EK0893336 | 2022-05-20 → 2023-02-13, 2023-11-18 → 2025-12-04, 2026-10-10 → (in service) | 775,894 |
| B3 087231009127 | EK0943226 | 2023-02-14 → 2023-11-18 | 222,806 |

| epoch | body | lens | nights | frames |
|---|---|---|---|---|
| 2021-07-10 → 2022-02-23 | B1 | 7220000552 | 202 | 174,586 |
| 2022-02-23 → 2022-05-20 | B1 | 7520000165 | 78 | 61,881 |
| 2022-05-20 → 2023-02-13 | B2 | 7220000552 | 195 | 164,625 |
| 2023-02-14 → 2023-11-18 | B3 | 7220000545 | 261 | 222,806 |
| 2023-11-18 → 2025-12-04 | B2 | 7220000552 | 725 | 611,133 |
| 2025-12-04 → 2026-07-18 | B1 | 7520000165 | 224 | 197,448 |
| 2026-10-10 → | B2 | 7220000552 | 21 | 16,789 |

The archive averages ~850 frames per night (B2's 2023–25 epoch: 611,133 frames over 725 nights), so a body in continuous service adds roughly 0.3 M actuations a year. Re-run `build_unit_history.py` to update the counts; it rewrites `index/unit_epochs.parquet` and prints the per-body totals.
**Directory dates.** 2021-07 → 2022-05 directories are UTC dates, not Rubin nights (EXIF time − dir date ≈ −12 h), so each holds the end of one night and the start of the next. From v4 every frame carries `night` (EXIF time − 12 h); nightly tables are keyed on it, while `(day_obs = directory date, seq)` stays the unique frame key.

### Pipeline history (`allsky_reduce.py` v4 → v6, deep index)
v4 (2026-10-10, full re-reduction of all nights): records `unit` and `night` per frame. Every night is re-reduced, so the 1,052 nights still on v1 now get the v3 matcher and moon handling. Under v1, full-moon nights failed 51 % of dark frames, and some failed all of them (e.g. 2025-06-10: 0/656 solved; 656/656 under v4). The running astrometric solution is now seeded from the nearest solved night *of the same unit* and switches seed mid-night on a swap day. Previously it took the nearest night of any unit, or the 2026 bootstrap (unit `9118/0165/8`), so it could start from the wrong camera's geometry. Frames whose EXIF clock is > 2 days from the directory date are skipped (`bad_exif_time`; 20 frames on 2025-12-04 stamped 2024-12-03). The completeness model is per unit × month (`YYYYMM|unit`, then the same unit's nearest month ≤ 3 months, then the whole-unit table, then the lens epoch). The old per-month tables mixed units in swap months; the clear-sky reference then came mostly from the sharper unit and left a 0.1–0.3 floor on the softer unit's clear nights (Feb 2023: 0.60 cloudy vs nowcast 0.00). The v3 products are kept in `snapshot_v3_20261010/`.
v5 (2026-10-10, the full re-reduction actually run): v4 plus looser DAOStarFinder shape cuts (`DAO_SHAPE`: sharpness 0.05–2.0, roundness ±1.5; was 0.1–1.2, ±0.8). The old cuts rejected the soft, elongated off-axis PSFs of the defocused configurations. On a 106-night clear-sky sample, V<5 completeness went from 0.67–0.84 to 0.90–1.00 in every configuration, and at 20–30° altitude from 0.53–0.72 to 0.96–1.00, for +0.005–0.014 chance matches. Best configuration for cloud measurement: B1 + lens 7520000165 at 8 mm, Feb–May 2022 (zenith FWHM 1.4 px); lens 7220000552 was the softest in every stint (2.7–3.5 px). Focus is the main variable: the same B1 + 7520000165 unit was 2.6 px in 2025–26.
Night solution on cloudy nights (2026-10-11): `calib/astrometry/<day_obs>.json` is written from the best frame with > 100 matches, or, if none, from refine frames with ≥ 40 matches and rms < 0.8 px. The allskycam was re-mounted 4.6° in roll between 2022-05 and the 2026-10-10 restart, and that cloudy first night had no frame above 100 matches; seeded from the 2022 solution only 22/515 dark frames solved, from the night's own geometry 95/515.

v6 (2026-10-15, nights 2026-10-10 → 10-14 only): after the restart the 8–15 mm zoom of 8323/0552 creeps: f = 759 → 842 px/rad (+11 %) over four nights, up to 1 %/h on 10-11. The EXIF focal tag flips 8 → 9 mm partway through 10-12, so v5 seeded the "9 mm" frames from 2024-08-04, a solution from before the re-mount (f 888, tilt/roll off), and 10-12/13 solved 0–1 frames. v6 matches seeds on body + lens only (`optics()`). It also scans plate scale ±12 % before the refine when the running solution matches < 60 % of bright stars, keeps the scan only for a ≥ 1.5× gain in matches, and falls back to the v5 path if the scanned scale fails. Solved dark frames: 10-11 289 → 555/556, 10-14 399 → 511/551; rms 0.50 px median. 10-12 (moon-lit haze) and 10-13 (overcast) are cloudy in the images and stay unsolved. The geometry is otherwise fixed to < 1 px: centre (1672.6, 1111.9) ± 0.3 px, tilt 3.85°, roll 259.515°, k1 −0.038. Only the plate scale moves, and it tracks the disk radius (f ≈ 0.685 R, r = 0.995). Night solutions: `calib/astrometry/20261011.json` (f 768.4, 535 frames), `20261014.json` (f 838.3, 414 frames). The v5 products for 10-10 are in `snapshot_pre_newunit_20261015/`.
Completeness model and cloud index (2026-10-16): tables are keyed per **service stint** (body/lens + first night, e.g. `202610|8323/0552@20261010`; `allsky_units.stint_keys()`), no longer per `body/lens/focal`. The focal tag split one mount's month into two tables. Also, 8323/0552 has served three stints (2022-05, 2023-11, 2026-10), each re-mounted and refocused. The new stint got its own table from 1,089 dark frames (`STINT_MIN = 800`); the 10-10 frames had fallen back to the whole-unit table that pooled 2022–25. Clear 10-11 now has cloud index median 0.00 (3.6 % of frames > 0.3). Earlier stints: 52 nights move by more than 0.01 on some frames, all in months where the focal tag had split the table, and the largest night-mean change is −0.04 (2022-05-20). Pre-change model and summary tables are in `snapshot_pre_newunit_20261015/`.
Focus, 8323/0552 since the restart (Gaussian FWHM of V < 3.5 stars, alt > 35°, raw green plane): 10-11 2.7 px, 10-14 2.8 px, 10-15 2.6 px (first 1.5 h, moon at 43°). That is between B1 + 7520000165 in 2022 (1.4 px) and this lens's earlier stints (2.7–3.5 px). The plate scale changed 11 % over the same nights with no matching FWHM change, so the zoom creep is not defocusing the lens.
**Refocus 2026-10-16** (daytime visit, EXIF focal tag 9 → 8 mm between 12:00 and 17:00 UTC): star FWHM 2.6 → 1.4 px (same 32 stars: ratio 0.53; DAO sharpness 0.40 → 1.08), plate scale 848 → 752 px/rad. Centre and roll are unchanged to < 1 px / 0.02°. 1.4 px equals the best configuration on record (9118/0165, 2022-02 → 05). `allsky_units.BREAKS` starts a new stint `8323/0552@20261016`. Until it has `STINT_MIN` dark frames of its own (about two clear nights), `cloud_metric.table_for` uses `allsky_units.PROXY`, the 9118/0165@20220223 table (same focus, f 750 px/rad). Without the split, the 2.7-px reference would under-predict the sharper camera's star counts and read thin cloud as clear. Re-run `finalize_rerun.sh` after a couple of clear nights so the stint gets its own table. `focus_check.py` measures FWHM (`focus_check.py out.parquet 20261016:best10 20261015:utc23:00-02:00/20`).
Catch-up 2026-10-28 (nights 2026-10-18 → 10-27, `index/nights_catchup_20261028.txt`, then `finalize_rerun.sh`): the 10-16 stint now has its own table (`202610|8323/0552@20261016`), so `PROXY` is no longer used for it; nights 10-16/17 moved by ≤ 0.007 in index, no other night changed. The zoom creeps again after the refocus: f 755 → 862 px/rad (+14 %) by 10-27, EXIF focal tag 8 → 9 mm on 10-18, but star FWHM stays 1.4 px (10-17, 10-22, 10-24, 10-27) and clear nights solve on every frame. Pre-catch-up products are in `snapshot_pre_catchup_20261028/`.

**Deep index (2026-10-30, parallel to the standard one).** The V<5.5 BSC index leaves about 60 % of the NSIDE-8 cells above 20° with < 3 expected stars, and its stars sit 1.5–2 mag above the detection limit, so it does not see thin cloud (0.5 mag of grey extinction removes ~1 % of them). `deep_match.py` matches Hipparcos V<7.5 to every stored detection with no CR2 re-read: it uses the frame's own solution (`maps/ astrometry_p`), applies proper motion, matches within 2 px, and drops stars with a brighter-than-V+1 neighbour within 0.3°. It then records the chance rate at positions offset 15 px. `build_completeness_deep.py` builds the same stint × month model as `build_completeness.py` with finer V bins. Reference frames are fd4_far ≥ median, then the top 35 % of `fdeep_far` within each zenith-sky quartile (fd4_far alone admits thin-cloud frames). `cloud_metric_deep.py` writes `deep_cloud/` (`cloud_idx_deep`; `ext_deep`, the grey extinction in mag that matches the observed count, 0–3; per-cell maps at NSIDE 8 and 16 in `deep_cloud_pix/`). `build_deep_tables.py` writes `index/deep_cloud_all_frames.parquet` and `index/deep_nightly.parquet`. Run `finalize_deep.sh <list>` after `finalize_rerun.sh`; `follow_night.sh` does both. Deep clear-sky completeness at V 7.0–7.25 (alt > 45°, dark): 0.76 for 8323/0552@20261016 and 9118/0165@20220223 (FWHM 1.4 px), 0.02–0.12 for the soft stints. So the deep index measures transparency on the sharp stints, while on the soft ones it is close to the V<6 index. Keep the standard index as the 2021–26 record. On dark frames the median number of NSIDE-8 cells with ≥ 3 expected stars is 236 (standard: 105). The clear-sky floor (frames with standard index 0) is a median `cloud_idx_deep` of 0.01–0.02 and `ext_deep` of 0.01–0.03 mag in every stint except the 6-night 8323/0552@20261010 stint (0.09). Against DREAM (317 nights), frames the standard index calls clear (< 0.05) with `ext_deep` 0.4–0.8 mag have DREAM median extinction 0.28 mag (0.04 at `ext_deep` < 0.2), so the deep index finds thin cloud DREAM also sees. Products: `deep_matches/` 37 GB (~22 MB/night), `deep_cloud_pix/` 0.7 GB.

Per frame: fetch → EXIF time → skip if sun alt > −12° → decode green Bayer plane `[0::2,1::2]` → 8×-binned median background → disk centre/radius → DAOStarFinder (FWHM 4 px, 5σ on a **locally adaptive** noise map so moon glare / Milky Way do not flood the list) → tilt-aware fisheye astrometry against the Yale BSC (refine the running solution incl. plate scale; coarse roll/scale bootstrap if the allskycam moved; stars within 25° of the moon excluded; matched against **all** sharp detections, not the brightest 400) → match V<6 catalog stars (3 px) → zero point + airmass slope → HEALPix NSIDE 32 horizon-coordinate maps (n_cat, n_det, sky) → streak finder → 8×-binned image.

### Products under `ALLSKY_OUT` (~170 MB/night standard + ~22 MB/night deep)
| dir | content |
|---|---|
| `frames/<day_obs>.parquet` | one row per frame: t_mid, night, unit, sun/moon, n_det, astrometry quality (`ast_mode` refine/bootstrap/failed), `frac_det_alt30_V5/V4` (detected fraction of BSC stars alt>30°, >25° from the moon), `frac_det_alt30_V5_nearmoon`, zp, k_airmass, sky_zenith_adu_s, n_streaks, `pipe_version` |
| `frames_regated/` | same + offline re-gate columns (`ast_n_all`, `ast_ok`, `fd5_far`, `fd4_far`) from `regate_frames.py` |
| `cloud/<day_obs>.parquet`, `cloud_pix/` | **completeness-weighted cloud index** per frame (`cloud_idx` = 1 − observed/expected under the clear-sky model; `frac_sky_cloudy` = fraction of NSIDE-8 cells with index>0.5) and per NSIDE-8 pixel; from `cloud_metric.py` |
| `calib/clear_sky_completeness_v2.parquet` | P(detect \| V, alt, local sky) **per calendar month** (fallback: lens epoch 8/9a/9b/10 mm keyed on disk radius), from the clearest 35 % of dark frames of that month incl. moonlit ones (`build_completeness.py`, 1.1 G star samples). Completeness tracks allskycam **focus**, not just focal length (e.g. Feb–May 2022 FWHM 4 px vs 6.5 px otherwise; V<4.5 completeness 0.98 vs 0.75–0.90), so a per-month reference is required to keep the clear-sky cloud-index floor at 0 in every month. V>4.5 stars are lost under bright moon → handled by the model's sky-brightness axis, not by masking |
| `catalogs/` | every detection with alt/az |
| `matches/` | every BSC star V<6 above 5°: detected flag + instrumental mag (the input to per-pixel cloud maps and transparency) |
| `maps/<day_obs>.h5` | `n_cat`, `n_det`, `sky` [nframe, 12288] NSIDE 32 (theta = zenith angle, phi = azimuth N=0 E=90, same as DREAM); `img8` [nframe, 281, 421] uint16; `astrometry_p` |
| `streaks/` | elongated components (satellites / aircraft) |
| `calib/astrometry/<day_obs>.json` | per-night refined solution (used as the seed for the nearest unsolved night) |
| `deep_matches/`, `deep_frames/`, `deep_cloud/`, `deep_cloud_pix/` | deep (Hipparcos V<7.5) match and cloud index, see *Deep index* above; model `calib/clear_sky_completeness_deep.parquet` |
| `index/` | `frame_index.parquet` (1.45 M frames), `night_index.parquet`, `night_ephemeris.parquet`, night lists |

### Analysis-side scripts (issue 6)
Supporting scripts: `sample_dream.py` (DREAM cloud maps from the LFA, 1 per 10 min, rotated to horizon coords; superseded for analysis by `build_dream_dense.py`, which takes **every** map at ~32 s cadence and also writes the DREAM extinction at each LSSTCam pointing and a cell-by-cell comparison with the allskycam into `$SYSTEM_PERFORMANCE_DATA_DIR/dream_*.parquet` for §3.1 of `allsky_cloud_analysis.ipynb`), `build_nightly.py` (per-night join of allskycam products with Scheduler/EFD/ConsDB/nowcast/DREAM records → `index/allsky_nightly.parquet`).

allskycam vs DREAM side-by-side (`fetch_night_demo.py`, `render_cam_dream.py`): `fetch_night_demo.py <day_obs> [--full seq ...]` pulls the night's raw CR2 frames (4×-binned green plane) and **every** DREAM `cloud_sys` map (rotated to horizon coordinates) into `OUT/demo/<day_obs>/`.
`render_cam_dream.py <day_obs> --seq N --out f.png` draws one frame: allskycam pixels + detected/missed BSC stars, NSIDE-8 cloud-index map, metrics / DREAM native NSIDE-32 extinction, NSIDE-8 mean, metrics / whole-night time-series strip. Every sky panel is in the allskycam pixel frame through the per-frame astrometric solution (E up, N right). `--movie [--t0 HH:MM --t1 HH:MM] --fps 12` renders one PNG per allskycam minute and encodes an H.264 mp4 (ffmpeg from the lsst-scipipe env). Example products in `figures/` (night 2025-09-19: broken cloud 23:30–04:30 UTC, then clear). Orientation check: per-cell correlation allskycam index vs DREAM extinction is r≈0.6 with the identity azimuth mapping and ≈0.1–0.2 for mirrored / rotated alternatives, so `sample_dream.to_horizon` has the right handedness.

### Astrometry failures (`ast_mode == 'failed'`)
A failed gate does **not** void the frame: the running (or nearest-night) solution is still applied and the cloud metrics are computed. In the v1 run 27 % of frames failed; ~40 % of those were matcher artefacts (brightest-400 list dominated by moon glare / Milky Way knots) fixed in v2, and a cluster of weeks with 2 px rms came from an inherited plate scale the refine could not adjust (fixed in v3). The rest are frames with no stars, i.e. overcast. Validation on 121 Scheduler-flag nights: P(cloud_idx>0.3 | WEATHER)=0.69, P(cloud_idx>0.3 | OPERATIONAL)=0.05, independent of moon altitude; per-night r=0.76. Of WEATHER frames the allskycam calls clear, 9 % are RH/dew-point/wind closures and the median is 74 min after the last cloudy frame (observers waiting for stable conditions / flag latency).

Products in `cloud/` use the v2 (per-epoch) model; `finalize_rerun.sh` rebuilds model + cloud products after any re-run.

**v3 re-run of 425 high-rms nights (2026-10-04).** A *solved* v1 frame could still carry a mis-registered solution (night median 1.4–2.0 px rms; the refine could not adjust the inherited plate scale), which drops ~half the predicted stars outside the 3-px match and leaves a flat cloud index of 0.3–0.6 on clear nights (e.g. 2025-07-17). Diagnostic: the night's 10th-percentile index sits in 0.1–0.7 (real cloud has clear gaps, overcast is 1). `index/nights_rerun_v3_rms.txt` lists the nights; after the v3 re-run they solve at 0.7–1.2 px and 10 nights remain above 1.4 px. The downtime notebook applies `CAM_RMS_MAX = 1.4` as a safeguard. Un-gated five-year fraction (index > 0.3) went 0.24 → 0.18.

Astrometric bootstrap: `calib/astrometry_bootstrap_clear.json` was solved on 2026-07-14 05:00 UTC (1290 stars, 0.53 px rms).
