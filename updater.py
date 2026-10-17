"""Public GitHub release updates for the portable Windows application.

No credentials or tally data are sent. Only the executable is replaced.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

VERSION = "0.3.1"
REPOSITORY = "AdamChesters/FrodoTappins-There-And-Backspace-Again"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=100"
MAX_EXE_BYTES = 128 * 1024 * 1024


def version_key(tag):
    """Accept historic v0.2 tags and new stable major.minor.patch releases."""
    match = re.fullmatch(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?", tag)
    if not match:
        raise ValueError("Not a stable version")
    return tuple(int(x or 0) for x in match.groups())


def select_release(releases, current=VERSION):
    if not isinstance(releases, list):
        raise ValueError("GitHub returned an unexpected release list.")
    latest = None
    for release in releases:
        try:
            if release.get("draft", True) or release.get("prerelease", True):
                continue
            tag = release["tag_name"]
            key = version_key(tag)
            if key <= version_key(current) or (latest and key <= version_key(latest["tag"])):
                continue
            latest = {"tag": tag, "asset": None}
            for asset in release.get("assets", []):
                digest = asset.get("digest") or ""
                size = asset.get("size")
                if (asset.get("name") == "FrodoTappins.exe"
                        and asset.get("state") == "uploaded"
                        and type(size) is int and 0 < size <= MAX_EXE_BYTES
                        and re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest)
                        and asset.get("browser_download_url") ==
                        f"{RELEASES_URL}/download/{tag}/FrodoTappins.exe"):
                    latest["asset"] = {"url": asset["browser_download_url"],
                                       "size": size, "sha256": digest[7:].lower()}
                    break
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return latest


class GitHubRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.hostname not in
            {"api.github.com", "github.com", "release-assets.githubusercontent.com",
             "objects.githubusercontent.com"}):
        raise ValueError("Update URL is not an approved GitHub HTTPS address.")


def open_url(url):
    validate_url(url)
    return urllib.request.build_opener(GitHubRedirects()).open(
        urllib.request.Request(url, headers={"User-Agent": f"FrodoTappins/{VERSION}",
                                           "Accept": "application/vnd.github+json"}),
        timeout=15)


def check_release():
    with open_url(API_URL) as response:
        body = response.read(4 * 1024 * 1024 + 1)
    if len(body) > 4 * 1024 * 1024:
        raise ValueError("GitHub release response is too large.")
    return select_release(json.loads(body))


def verify_executable(path, asset):
    if path.stat().st_size != asset["size"]:
        raise ValueError("Update size did not match GitHub. Try again.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != asset["sha256"]:
        raise ValueError("Update checksum did not match GitHub. Try again.")
    with path.open("rb") as stream:
        header = stream.read(64)
        if len(header) < 64 or header[:2] != b"MZ":
            raise ValueError("Update is not a Windows executable.")
        stream.seek(struct.unpack_from("<I", header, 60)[0])
        if stream.read(6) != b"PE\x00\x00\x64\x86":
            raise ValueError("Update is not a Windows x64 executable.")


def download_release(release, target, cancelled, progress):
    """Stage on the target volume; remove incomplete downloads on every failure."""
    asset = release["asset"]
    if not asset:
        raise ValueError("This release has no verified executable. Open Releases to download it.")
    stage = Path(tempfile.mkdtemp(prefix=".FrodoTappins-update-", dir=target.parent))
    try:
        output = stage / "new.exe"
        deadline = time.monotonic() + 180
        size = 0
        with open_url(asset["url"]) as response, output.open("wb") as stream:
            while True:
                if cancelled.is_set():
                    raise RuntimeError("Update cancelled.")
                if time.monotonic() > deadline:
                    raise TimeoutError("Update download timed out. Try again.")
                chunk = response.read(128 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > asset["size"]:
                    raise ValueError("Update exceeded its expected size.")
                stream.write(chunk)
                progress(int(size * 100 / asset["size"]))
        verify_executable(output, asset)
        if cancelled.is_set():
            raise RuntimeError("Update cancelled.")
        return stage
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def start_helper(stage, target, asset):
    if os.name != "nt" or not getattr(sys, "frozen", False):
        raise RuntimeError("Automatic installation requires the Windows portable EXE.")
    helper = stage / "helper.exe"
    shutil.copy2(sys.executable, helper)
    (stage / "manifest.json").write_text(json.dumps({
        "pid": os.getpid(), "target": str(target.resolve()), "asset": asset,
        "minimized": "--minimized" in sys.argv}), encoding="utf-8")
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    process = subprocess.Popen([str(helper), "--apply-update", str(stage)],
                               env=env, creationflags=0x08000000)
    deadline = time.monotonic() + 30
    while not (stage / "ready").exists():
        if process.poll() is not None or time.monotonic() > deadline:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            raise RuntimeError("Update helper could not start. Your app has not been replaced.")
        time.sleep(0.1)
    return process


def apply_update(stage):
    """Run only in a copy of the old frozen app, before GUI/input initialization."""
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                 wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    stage = Path(stage).resolve()
    handle = None
    target = None
    backup = stage / "previous.exe"
    replaced = False
    try:
        manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
        target = Path(manifest["target"]).resolve()
        if stage.parent != target.parent or Path(sys.executable).resolve() != stage / "helper.exe":
            raise ValueError("Invalid update location.")
        handle = kernel.OpenProcess(0x100000 | 0x1000, False, manifest["pid"])
        if not handle:
            raise OSError("Cannot open the running app.")
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            raise OSError("Cannot verify the running app.")
        if Path(buffer.value).resolve() != target:
            raise ValueError("Update target does not match the running app.")
        verify_executable(stage / "new.exe", manifest["asset"])
        (stage / "ready").touch()
        if kernel.WaitForSingleObject(handle, 120000) != 0:
            raise TimeoutError("App did not close. No files were replaced.")
        # The app writes approval only after its final tally save succeeds.
        if not (stage / "install").exists():
            return 0  # Normal shutdown/cancellation before the final save.
        verify_executable(stage / "new.exe", manifest["asset"])
        shutil.copy2(target, backup)
        for attempt in range(50):
            try:
                os.replace(stage / "new.exe", target)
                replaced = True
                break
            except PermissionError:
                if attempt == 49:
                    raise
                time.sleep(0.2)
        args = [str(target)] + (["--minimized"] if manifest.get("minimized") else [])
        subprocess.Popen(args, cwd=target.parent,
                         env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"))
    except Exception as error:
        if replaced and target and backup.exists():
            shutil.copy2(backup, target)
            subprocess.Popen([str(target)], cwd=target.parent,
                             env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"))
        (stage / "error.txt").write_text(str(error), encoding="utf-8")
        ctypes.windll.user32.MessageBoxW(None, f"Update failed: {error}\nYour tally files were not changed.",
                                        "FrodoTappins update", 0x10)
        return 1
    finally:
        if handle:
            kernel.CloseHandle(handle)
    return 0
