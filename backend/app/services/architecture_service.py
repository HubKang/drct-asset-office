from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Iterable
from uuid import uuid4

from fastapi import HTTPException

from backend.app.core.config import PROJECT_ROOT, now_kst


@dataclass(frozen=True)
class FolderPolicy:
    category: str
    policy: str
    role: str
    risk_level: str
    deep_scan: bool = True
    scan_note: str | None = None


class ArchitectureService:
    def __init__(self) -> None:
        self.root = PROJECT_ROOT
        self.logs_dir = self.root / "logs"
        self.archive_root = self.root / "archive" / "cleanup"
        self.history_file = self.logs_dir / "architecture_cleanup_history.jsonl"

        self.protected_exact = {
            ".env",
            "backend/.env",
            "frontend/.env",
            "db/drct_asset.sqlite3",
            "requirements.txt",
            "frontend/package.json",
            "frontend/package-lock.json",
        }
        self.protected_prefixes = {
            "db",
            "data/trade_journal_images",
            "backend/.local/telegram_sessions",
            "backend",
            "frontend/src",
            "scripts",
            "docs",
        }
        self.safe_delete_prefixes = {
            ".cache",
            ".mpltcache",
            "frontend/.vite",
            "frontend/dist",
        }
        self.review_required_roots = {"marcap", "agents", "prompts", "knowledge", "data_cache"}

        self.folder_policies: dict[str, FolderPolicy] = {
            "backend": FolderPolicy("backend_source", "keep", "FastAPI 백엔드 소스", "low"),
            "frontend": FolderPolicy("frontend_source", "keep", "React/Vite 프론트 소스", "low"),
            "docs": FolderPolicy("documentation", "keep", "설계/운영 문서", "low"),
            "scripts": FolderPolicy("source_code", "keep", "운영 스크립트", "low"),
            "db": FolderPolicy("protected", "protected", "운영 DB 저장소", "critical"),
            "data": FolderPolicy("operational_data", "protected", "업로드/정적 운영 데이터", "high"),
            "data/trade_journal_images": FolderPolicy("upload_data", "protected", "매매일지 이미지 업로드", "critical"),
            ".env": FolderPolicy("protected", "protected", "운영 환경변수", "critical", deep_scan=False),
            "backend/.local/telegram_sessions": FolderPolicy("protected", "protected", "텔레그램 세션", "critical"),
            ".venv": FolderPolicy(
                "dependency",
                "gitignored_recommended",
                "Python 가상환경",
                "medium",
                deep_scan=False,
                scan_note="대용량: 얕은 스캔",
            ),
            "frontend/node_modules": FolderPolicy(
                "dependency",
                "gitignored_recommended",
                "Node 의존성",
                "medium",
                deep_scan=False,
                scan_note="대용량: 얕은 스캔",
            ),
            "frontend/dist": FolderPolicy("build_artifact", "cleanup_candidate", "프론트 빌드 산출물", "low"),
            "frontend/.vite": FolderPolicy("build_artifact", "cleanup_candidate", "Vite 캐시", "low"),
            "data_cache": FolderPolicy("cache", "review_required", "중간 캐시 데이터", "medium"),
            ".cache": FolderPolicy("cache", "cleanup_candidate", "실행 캐시", "low"),
            ".mpltcache": FolderPolicy("cache", "cleanup_candidate", "matplotlib 캐시", "low"),
            "marcap": FolderPolicy("legacy_or_review_required", "review_required", "시장 데이터 자산(참조 확인 필요)", "medium"),
            "agents": FolderPolicy("legacy_or_review_required", "review_required", "에이전트 자산(참조 확인 필요)", "medium"),
            "knowledge": FolderPolicy("knowledge_asset", "review_required", "지식 자산", "medium"),
            "prompts": FolderPolicy("prompt_asset", "review_required", "프롬프트 자산", "medium"),
            "archive/cleanup": FolderPolicy("build_artifact", "keep", "정리 보관본", "low"),
            "logs": FolderPolicy("operational_data", "gitignored_recommended", "운영 로그", "low"),
        }

        self.cleanup_defaults = {"data_cache", ".cache", ".mpltcache", "frontend/dist", "frontend/.vite"}
        self.reference_includes = {".py", ".ts", ".tsx", ".md"}
        self.reference_exclude_dirs = {
            ".git",
            ".venv",
            "node_modules",
            "dist",
            "__pycache__",
            ".cache",
            ".mpltcache",
            "db",
            "data",
            "archive",
            "frontend/.vite",
        }

    def get_folder_status(self) -> dict[str, object]:
        scanned_at = now_kst()
        items: list[dict[str, object]] = []
        total_size = 0
        operational_size = 0
        cache_artifact_size = 0
        cleanup_candidate_size = 0

        for relative_path, policy in self.folder_policies.items():
            abs_path = self.root / relative_path
            exists = abs_path.exists()
            size_bytes, file_count, latest_mtime = self._scan_path(abs_path, deep_scan=policy.deep_scan) if exists else (0, 0, None)
            item = {
                "path": relative_path,
                "exists": exists,
                "category": policy.category,
                "policy": policy.policy,
                "role": policy.role,
                "risk_level": policy.risk_level,
                "size_bytes": size_bytes,
                "file_count": file_count,
                "latest_modified_at": self._fmt_mtime(latest_mtime),
                "scan_note": policy.scan_note,
            }
            items.append(item)
            total_size += size_bytes
            if policy.category in {"operational_data", "upload_data", "protected"}:
                operational_size += size_bytes
            if policy.category in {"cache", "build_artifact"}:
                cache_artifact_size += size_bytes
            if policy.policy in {"cleanup_candidate", "archive_candidate"}:
                cleanup_candidate_size += size_bytes

        items.sort(key=lambda x: x["path"])
        return {
            "scanned_at": scanned_at,
            "total_size_bytes": total_size,
            "operational_data_size_bytes": operational_size,
            "cache_and_artifact_size_bytes": cache_artifact_size,
            "cleanup_candidate_size_bytes": cleanup_candidate_size,
            "items": items,
        }

    def get_cleanup_candidates(self) -> dict[str, object]:
        scanned_at = now_kst()
        items: list[dict[str, object]] = []
        for path in sorted(self.cleanup_defaults):
            items.append(self._status_item_for_path(path, "default_cleanup"))
        for p in self._glob_paths("__pycache__"):
            items.append(self._status_item_for_path(p.relative_to(self.root).as_posix(), "python_cache"))
        for p in self._glob_files("*.pyc"):
            items.append(self._status_item_for_path(p.relative_to(self.root).as_posix(), "python_cache_file", is_file=True))
        for path in ["marcap", "agents", "prompts", "knowledge", "data_cache"]:
            items.append(self._status_item_for_path(path, "review_required"))
        unique = {x["path"]: x for x in items}
        return {"scanned_at": scanned_at, "items": sorted(unique.values(), key=lambda x: x["path"])}

    def reference_check(self, path: str) -> dict[str, object]:
        if not path.strip():
            raise HTTPException(status_code=400, detail="path is required")
        target = path.strip()
        needles = {target, Path(target).name}
        matches: list[dict[str, object]] = []
        matched_files: set[str] = set()
        for file_path in self._iter_reference_files():
            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    for idx, line in enumerate(f, start=1):
                        if any(n in line for n in needles):
                            rel = file_path.relative_to(self.root).as_posix()
                            matched_files.add(rel)
                            matches.append({"file_path": rel, "line_no": idx, "snippet": line.strip()[:220]})
            except OSError:
                continue
        return {"path": target, "reference_count": len(matches), "matched_files": sorted(matched_files), "matches": matches[:500]}

    def cleanup(self, targets: list[str], mode: str, confirm: bool) -> dict[str, object]:
        if mode != "archive":
            raise HTTPException(status_code=400, detail="only archive mode is supported")
        if not confirm:
            raise HTTPException(status_code=400, detail="confirm=true is required")
        if not targets:
            raise HTTPException(status_code=400, detail="targets is required")

        run_id = uuid4().hex[:12]
        executed_at = now_kst()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_archive_dir = self.archive_root / stamp
        run_archive_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        results: list[dict[str, object]] = []

        for target in targets:
            res = self._cleanup_single_target(target.strip(), run_archive_dir)
            self._append_history({"run_id": run_id, "executed_at": executed_at, "mode": mode, **res})
            results.append(res)

        return {"run_id": run_id, "executed_at": executed_at, "mode": mode, "results": results}

    def cleanup_history(self) -> dict[str, object]:
        if not self.history_file.exists():
            return {"items": []}
        items: list[dict[str, object]] = []
        with self.history_file.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        items.sort(key=lambda x: x.get("executed_at", ""), reverse=True)
        return {"items": items}

    def get_delete_eligibility(self) -> dict[str, object]:
        scanned_at = now_kst()
        candidates = self.get_cleanup_candidates()["items"]
        status_items = self.get_folder_status()["items"]
        history = self.cleanup_history()["items"]
        history_map = self._history_map(history)
        paths = {x["path"] for x in candidates} | {x["path"] for x in status_items}
        archive_entries = list(self._scan_archive_entries())
        for entry in archive_entries:
            paths.add(entry)

        items: list[dict[str, object]] = []
        for path in sorted(paths):
            abs_path = self.root / path
            exists = abs_path.exists()
            size_bytes, file_count, mtime = self._scan_path(abs_path, deep_scan=True) if exists else (0, 0, None)
            category, policy, risk = self._resolve_meta(path)
            deletion_status, deletion_label, delete_reason, protected_reason = self._evaluate_deletion(path, history_map.get(path))

            reference_count = None
            if path.split("/")[0] in self.review_required_roots:
                reference_count = self._quick_reference_count(path)
                if reference_count > 0 and deletion_status not in {"protected", "archive_delete_blocked"}:
                    deletion_status = "blocked_by_reference"
                    deletion_label = "코드 참조 있음"
                    delete_reason = f"현재 소스/문서에서 {reference_count}건 참조가 발견되었습니다."

            items.append(
                {
                    "path": path,
                    "category": category,
                    "policy": policy,
                    "deletion_status": deletion_status,
                    "deletion_label": deletion_label,
                    "delete_reason": delete_reason,
                    "risk_level": risk,
                    "reference_count": reference_count,
                    "is_git_tracked": self._is_git_tracked(path),
                    "is_archived": path.startswith("archive/cleanup/"),
                    "cleanup_history_status": history_map.get(path),
                    "protected_reason": protected_reason,
                    "size_bytes": size_bytes,
                    "file_count": file_count,
                    "last_modified_at": self._fmt_mtime(mtime),
                }
            )
        return {"scanned_at": scanned_at, "items": items}

    def delete_safe_candidates(self, targets: list[str], confirm_text: str) -> dict[str, object]:
        if confirm_text != "삭제를 확인합니다":
            raise HTTPException(status_code=400, detail='confirm_text는 "삭제를 확인합니다"와 정확히 일치해야 합니다.')
        if not targets:
            raise HTTPException(status_code=400, detail="targets is required")

        eligibility = {x["path"]: x for x in self.get_delete_eligibility()["items"]}
        results: list[dict[str, object]] = []

        for target in targets:
            path = target.strip().replace("\\", "/").lstrip("./")
            item = eligibility.get(path)
            if not item:
                results.append({"target": path, "status": "skipped", "message": "판정 정보가 없어 삭제를 건너뜁니다.", "deleted_path": None})
                continue
            if item["deletion_status"] not in {"safe_to_delete", "archived_delete_candidate"}:
                results.append({"target": path, "status": "blocked", "message": f"삭제 불가 상태: {item['deletion_label']}", "deleted_path": None})
                continue

            abs_path = self.root / path
            if not abs_path.exists():
                results.append({"target": path, "status": "skipped", "message": "대상이 존재하지 않습니다.", "deleted_path": None})
                continue

            try:
                if abs_path.is_dir():
                    shutil.rmtree(abs_path)
                else:
                    abs_path.unlink(missing_ok=True)
                results.append({"target": path, "status": "deleted", "message": "안전 삭제 완료", "deleted_path": abs_path.as_posix()})
            except Exception as exc:
                results.append({"target": path, "status": "error", "message": str(exc), "deleted_path": None})

        return {"executed_at": now_kst(), "results": results}

    def _evaluate_deletion(self, path: str, history_status: str | None) -> tuple[str, str, str, str | None]:
        p = path.rstrip("/")
        root = p.split("/")[0]

        if p in self.protected_exact or any(p == x or p.startswith(x + "/") for x in self.protected_prefixes):
            return ("protected", "삭제 금지", "운영 필수 자산이므로 삭제 금지", "운영 필수 경로")

        if p.startswith("archive/cleanup/"):
            if any(k in p for k in ["db", ".env", "trade_journal_images", "telegram_sessions"]):
                return ("archive_delete_blocked", "Archive 삭제 보류", "민감 경로명이 포함되어 보류", None)
            if history_status in {"archived", "archived_copy_only"}:
                return ("archived_delete_candidate", "Archive 삭제 가능", "archive 보관본이며 삭제 가능 조건 충족", None)
            return ("archive_delete_blocked", "Archive 삭제 보류", "정리 이력이 불명확하여 보류", None)

        if "__pycache__" in p or p.endswith(".pyc") or any(p == x or p.startswith(x + "/") for x in self.safe_delete_prefixes):
            reason = "캐시/산출물 파일로 재생성 가능합니다."
            if self._is_git_tracked(p):
                reason += " Git 추적 여부 확인 필요. 삭제 전 git status 및 git ls-files 확인 권장."
            return ("safe_to_delete", "삭제 가능", reason, None)

        if root in self.review_required_roots:
            if root == "data_cache":
                return ("safe_to_delete_after_archive", "Archive 후 삭제 가능", "중간 캐시 데이터일 수 있어 먼저 archive 후 삭제 권장", None)
            return ("review_required", "사용 여부 확인 필요", "자산 폴더로 참조/운영 여부 확인이 필요합니다.", None)

        return ("unknown", "판단 불가", "자동 판정 규칙이 없는 경로입니다.", None)

    def _resolve_meta(self, path: str) -> tuple[str, str, str]:
        if path in self.folder_policies:
            p = self.folder_policies[path]
            return p.category, p.policy, p.risk_level
        root = path.split("/")[0]
        if root in self.folder_policies:
            p = self.folder_policies[root]
            return p.category, p.policy, p.risk_level
        return "cleanup_candidate", "review_required", "medium"

    def _quick_reference_count(self, path: str) -> int:
        return int(self.reference_check(path).get("reference_count") or 0)

    def _cleanup_single_target(self, target: str, run_archive_dir: Path) -> dict[str, object]:
        normalized = target.replace("\\", "/").lstrip("./")
        original_path = self.root / normalized
        original_str = original_path.as_posix()

        if self._is_protected_path(normalized):
            return {"target": normalized, "original_path": original_str, "archived_path": None, "size_bytes": 0, "file_count": 0, "status": "blocked", "message": "protected 대상은 archive 금지"}
        if not original_path.exists():
            return {"target": normalized, "original_path": original_str, "archived_path": None, "size_bytes": 0, "file_count": 0, "status": "skipped", "message": "대상이 존재하지 않음"}

        size_bytes, file_count, _ = self._scan_path(original_path, deep_scan=True)
        safe_name = normalized.replace("/", "__")
        dest = run_archive_dir / safe_name
        if dest.exists():
            dest = run_archive_dir / f"{safe_name}__{uuid4().hex[:6]}"

        try:
            shutil.move(str(original_path), str(dest))
            return {"target": normalized, "original_path": original_str, "archived_path": dest.as_posix(), "size_bytes": size_bytes, "file_count": file_count, "status": "archived", "message": "archive 이동 완료"}
        except Exception as exc:
            try:
                fallback_dest = dest if not dest.exists() else run_archive_dir / f"{safe_name}__{uuid4().hex[:6]}"
                if original_path.is_dir():
                    shutil.copytree(str(original_path), str(fallback_dest), dirs_exist_ok=True)
                else:
                    fallback_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(original_path), str(fallback_dest))
                return {
                    "target": normalized,
                    "original_path": original_str,
                    "archived_path": fallback_dest.as_posix(),
                    "size_bytes": size_bytes,
                    "file_count": file_count,
                    "status": "archived_copy_only",
                    "message": f"이동 실패로 복사만 완료: {exc}",
                }
            except Exception as fallback_exc:
                return {
                    "target": normalized,
                    "original_path": original_str,
                    "archived_path": None,
                    "size_bytes": size_bytes,
                    "file_count": file_count,
                    "status": "error",
                    "message": f"{exc} / fallback_copy_error: {fallback_exc}",
                }

    def _append_history(self, row: dict[str, object]) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        with self.history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _status_item_for_path(self, path: str, candidate_type: str, is_file: bool = False) -> dict[str, object]:
        category, policy, risk = self._resolve_meta(path)
        abs_path = self.root / path
        exists = abs_path.exists()
        size_bytes, file_count, latest_mtime = self._scan_path(abs_path, deep_scan=True, is_file=is_file) if exists else (0, 0, None)
        return {
            "path": path,
            "candidate_type": candidate_type,
            "category": category,
            "policy": policy,
            "risk_level": risk,
            "size_bytes": size_bytes,
            "file_count": file_count,
            "latest_modified_at": self._fmt_mtime(latest_mtime),
        }

    def _scan_path(self, path: Path, deep_scan: bool, is_file: bool = False) -> tuple[int, int, float | None]:
        if is_file and path.is_file():
            st = path.stat()
            return st.st_size, 1, st.st_mtime
        if path.is_file():
            st = path.stat()
            return st.st_size, 1, st.st_mtime
        if not path.exists():
            return 0, 0, None

        total_size = 0
        file_count = 0
        latest = None
        if not deep_scan:
            for child in path.iterdir():
                if child.is_file():
                    st = child.stat()
                    total_size += st.st_size
                    file_count += 1
                    latest = st.st_mtime if latest is None else max(latest, st.st_mtime)
            return total_size, file_count, latest

        for root, dirs, files in os.walk(path, topdown=True):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".venv"}]
            for name in files:
                file_path = Path(root) / name
                try:
                    st = file_path.stat()
                except OSError:
                    continue
                total_size += st.st_size
                file_count += 1
                latest = st.st_mtime if latest is None else max(latest, st.st_mtime)
        return total_size, file_count, latest

    def _fmt_mtime(self, mtime: float | None) -> str | None:
        if mtime is None:
            return None
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

    def _glob_paths(self, dirname: str) -> Iterable[Path]:
        for root, dirs, _ in os.walk(self.root, topdown=True):
            dirs[:] = [d for d in dirs if d not in {".git", ".venv", "node_modules"}]
            for d in dirs:
                if d == dirname:
                    yield Path(root) / d

    def _glob_files(self, pattern: str) -> Iterable[Path]:
        suffix = pattern.replace("*", "")
        for root, dirs, files in os.walk(self.root, topdown=True):
            dirs[:] = [d for d in dirs if d not in {".git", ".venv", "node_modules"}]
            for file_name in files:
                if file_name.endswith(suffix):
                    yield Path(root) / file_name

    def _iter_reference_files(self) -> Iterable[Path]:
        roots = [self.root / "backend", self.root / "frontend" / "src", self.root / "scripts", self.root / "docs", self.root]
        seen: set[Path] = set()
        for base in roots:
            if not base.exists():
                continue
            for root, dirs, files in os.walk(base, topdown=True):
                rel_root = Path(root).relative_to(self.root).as_posix()
                dirs[:] = [d for d in dirs if d not in self.reference_exclude_dirs and f"{rel_root}/{d}" not in self.reference_exclude_dirs]
                for name in files:
                    p = Path(root) / name
                    if p in seen:
                        continue
                    if p.suffix.lower() in self.reference_includes:
                        seen.add(p)
                        yield p

    def _is_git_tracked(self, path: str) -> bool | None:
        try:
            result = subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=str(self.root), capture_output=True, text=True, check=False)
            return result.returncode == 0
        except OSError:
            return None

    def _history_map(self, rows: list[dict[str, object]]) -> dict[str, str]:
        out: dict[str, str] = {}
        for row in rows:
            target = str(row.get("target") or "").replace("\\", "/")
            if target and target not in out:
                out[target] = str(row.get("status") or "")
        return out

    def _scan_archive_entries(self) -> Iterable[str]:
        base = self.archive_root
        if not base.exists():
            return []
        entries: list[str] = []
        for stamp_dir in base.iterdir():
            if not stamp_dir.is_dir():
                continue
            for child in stamp_dir.iterdir():
                entries.append(child.relative_to(self.root).as_posix())
        return entries

    def _is_protected_path(self, relative_path: str) -> bool:
        p = relative_path.replace("\\", "/").rstrip("/")
        if p in self.protected_exact:
            return True
        return any(p == x or p.startswith(x + "/") for x in self.protected_prefixes)
