"""Optional self-update helper.

By default this does nothing. It only pulls from a remote repo when
AUTO_UPDATE=true AND UPSTREAM_REPO is set, so a normal deploy can never
overwrite the local code by accident.
"""
from os import path as opath, getenv
from logging import FileHandler, StreamHandler, INFO, basicConfig, error as log_error, info as log_info
from subprocess import run as srun

from dotenv import load_dotenv

load_dotenv()

if opath.exists("log.txt"):
    with open("log.txt", "r+") as f:
        f.truncate(0)

basicConfig(
    format="[%(asctime)s] [%(name)s | %(levelname)s] - %(message)s [%(filename)s:%(lineno)d]",
    datefmt="%m/%d/%Y, %H:%M:%S %p",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)

AUTO_UPDATE = getenv("AUTO_UPDATE", "false").lower() == "true"
UPSTREAM_REPO = getenv("UPSTREAM_REPO")
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH")

if not AUTO_UPDATE or not UPSTREAM_REPO:
    log_info("Self-update disabled (set AUTO_UPDATE=true and UPSTREAM_REPO to enable). Skipping.")
    raise SystemExit(0)

if opath.exists(".git"):
    srun(["rm", "-rf", ".git"])

update = srun(
    [f"git init -q \
        && git config --global user.email openhands@all-hands.dev \
        && git config --global user.name openhands \
        && git add . \
        && git commit -sm update -q \
        && git remote add origin {UPSTREAM_REPO} \
        && git fetch origin -q \
        && git reset --hard origin/{UPSTREAM_BRANCH} -q"],
    shell=True,
)

if update.returncode == 0:
    log_info("Successfully updated with latest commit from UPSTREAM_REPO")
else:
    log_error("Something went wrong while updating, check UPSTREAM_REPO if valid or not!")
