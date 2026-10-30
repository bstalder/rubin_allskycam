"""Site configuration shared by the all-sky scripts: product root, raw archives, S3 access, external caches.

Every value can be overridden by the environment variable of the same name. The defaults are the USDF (SLAC S3DF)
locations used for the 2021-07 -> 2026-10 reduction.
"""

import os
from pathlib import Path


def _env(name, default):
    return os.environ.get(name, default)


# Product root. Default: data/allsky next to this file (not on USDF shared storage; set ALLSKY_OUT for real runs).
# The 2021-07 -> 2026-10 reduction lives at /sdf/data/rubin/user/stalder/allsky.
ALLSKY_OUT = Path(
    _env("ALLSKY_OUT", Path(__file__).resolve().parent / "data" / "allsky")
)

# Raw archives. disk: 2021-07-10 -> 2024-02-26 (utYYMMDD/ascYYMMDDNNNN.{cr2,jpg});
# LFA: 2024-02-06 -> present (s3://<bucket>/<prefix>YYYY/MM/DD/ascYYMMDDNNNN.{cr2,jpg}).
ALLSKY_DISK_ARCHIVE = _env(
    "ALLSKY_DISK_ARCHIVE", "/sdf/data/rubin/offline/allsky/storage"
)
LFA_BUCKET = _env("ALLSKY_LFA_BUCKET", "rubinobs-lfa-cp")
LFA_PREFIX = _env("ALLSKY_LFA_PREFIX", "AllSkyCamera/")

# S3 access: an AWS shared-credentials profile against the USDF S3 gateway.
S3_ENDPOINT = _env("ALLSKY_S3_ENDPOINT", "https://s3dfrgw.slac.stanford.edu/")
S3_PROFILE = _env("ALLSKY_S3_PROFILE", "lfa")
os.environ.setdefault(
    "AWS_SHARED_CREDENTIALS_FILE", os.path.expanduser("~/.lsst/aws-credentials.ini")
)

# External caches of the ROSP-11 system-performance analysis, built outside this repository.
# Optional for the reduction: build_completeness.py reads scheduler_observatory_status.parquet only when present.
SYSTEM_PERFORMANCE_DATA_DIR = Path(
    _env(
        "SYSTEM_PERFORMANCE_DATA_DIR",
        "/sdf/data/rubin/user/stalder/system_performance_data",
    )
)


def s3_client():
    """boto3 S3 client for the LFA (profile S3_PROFILE at S3_ENDPOINT)."""
    import boto3

    return boto3.Session(profile_name=S3_PROFILE).client("s3", endpoint_url=S3_ENDPOINT)
