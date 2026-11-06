#!/bin/bash
# Re-execute the weather notebooks after a re-reduction + finalize_rerun.sh so their outputs reflect the re-reduced camera record.
# The notebooks live in lsst/sp_notebooks, tracking_hub/ops/rosp-11_time_loss_accounting/; set ROSP11_DIR to that checkout's folder.
set -e
PY=/sdf/group/rubin/sw/conda/envs/lsst-scipipe-13.0.0/bin/python3
# The scheduler-simulation climatology is in rubin_notebooks; set CLIMATOLOGY_NB to that notebook.
# Order matters: the downtime notebook writes the nightly tables the climatology reads, and the
# climatology writes the monthly table the allskycam notebook's §5 reads.
ROSP11_DIR="${ROSP11_DIR:-$HOME/notebooks/sp_notebooks/tracking_hub/ops/rosp-11_time_loss_accounting}"
CLIMATOLOGY_NB="${CLIMATOLOGY_NB:-$HOME/notebooks/rubin_notebooks/earlyoperations/system_performance/weather_downtime_climatology.ipynb}"
export ROSP11_WRITE_RESULTS=1  # the notebooks only write their result files when asked
ROSP11_DIR="$ROSP11_DIR" CLIMATOLOGY_NB="$CLIMATOLOGY_NB" $PY - <<'PY'
import asyncio, nbformat, os, time
from nbclient import NotebookClient
r = os.environ["ROSP11_DIR"]
for path in [f"{r}/weather_downtime_analysis.ipynb", os.environ["CLIMATOLOGY_NB"], f"{r}/allsky_cloud_analysis.ipynb"]:
    nb = nbformat.read(path, as_version=4); t0 = time.time()
    NotebookClient(nb, timeout=1800, kernel_name="python3", resources={"metadata": {"path": os.path.dirname(path)}}, allow_errors=True).execute()
    nbformat.write(nb, path)
    errs = [(i, o["ename"]) for i, c in enumerate(nb.cells) if c.cell_type == "code" for o in c.get("outputs", []) if o.get("output_type") == "error"]
    print(f"{path}: ran in {time.time()-t0:.0f}s, errors: {errs}")
PY
