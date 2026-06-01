from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys


def run_cmd(args: list[str], env: dict[str, str] | None = None, timeout: int = 20) -> dict[str, object]:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, check=False, timeout=timeout, env=env)
        return {
            "cmd": " ".join(args),
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip()[:500],
            "stderr": (proc.stderr or "").strip()[:500],
        }
    except Exception as exc:
        return {"cmd": " ".join(args), "error": f"{exc.__class__.__name__}: {str(exc)[:300]}"}


def proxy_free_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy", "NO_PROXY", "no_proxy"):
        env.pop(key, None)
    return env


def detect_runtime() -> tuple[str | None, str | None]:
    for name in ("node", "deno", "bun", "qjs", "quickjs"):
        p = shutil.which(name)
        if p:
            return name, p
    return None, None


def main() -> int:
    env = proxy_free_env()
    runtime_name, runtime_path = detect_runtime()
    js_runtimes_value = os.getenv("YOUTUBE_TRANSCRIPT_YTDLP_JS_RUNTIMES", "").strip()
    selected_js_runtime = js_runtimes_value or (f"{runtime_name}:{runtime_path}" if runtime_name and runtime_path else "")

    result: dict[str, object] = {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "yt_dlp_importable": importlib.util.find_spec("yt_dlp") is not None,
        "env_youtube_transcript_ytdlp_js_runtimes": js_runtimes_value or None,
        "selected_js_runtime": selected_js_runtime or None,
    }
    result["pip_version"] = run_cmd([sys.executable, "-m", "pip", "--version"])
    result["pip_config_list"] = run_cmd([sys.executable, "-m", "pip", "config", "list"])
    result["yt_dlp_version"] = run_cmd([sys.executable, "-m", "yt_dlp", "--version"], env=env)
    result["runtime_checks"] = {
        "node": {"path": shutil.which("node"), "version": run_cmd(["node", "--version"]) if shutil.which("node") else None},
        "deno": {"path": shutil.which("deno"), "version": run_cmd(["deno", "--version"]) if shutil.which("deno") else None},
        "bun": {"path": shutil.which("bun"), "version": run_cmd(["bun", "--version"]) if shutil.which("bun") else None},
        "qjs": {"path": shutil.which("qjs"), "version": run_cmd(["qjs", "--version"]) if shutil.which("qjs") else None},
        "quickjs": {"path": shutil.which("quickjs"), "version": run_cmd(["quickjs", "--version"]) if shutil.which("quickjs") else None},
    }

    test_video = "TKdWMdxJZwg"
    list_subs_cmd = [sys.executable, "-m", "yt_dlp", "--list-subs"]
    if selected_js_runtime:
        list_subs_cmd.extend(["--js-runtimes", selected_js_runtime])
    list_subs_cmd.append(f"https://www.youtube.com/watch?v={test_video}")
    result["yt_dlp_list_subs_test"] = run_cmd(list_subs_cmd, env=env, timeout=45)

    result["install_hint"] = f"{sys.executable} -m pip install --no-cache-dir yt-dlp --index-url https://pypi.org/simple"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
