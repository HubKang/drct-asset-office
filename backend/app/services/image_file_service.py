from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import mimetypes
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import PROJECT_ROOT, now_kst


DOMAIN_FOLDERS = {
    "trade_journal": "trade_journal_images",
    "trade_method": "trade_method_images",
    "stock_tracking": "stock_tracking",
    "kms": "kms",
}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
WINDOWS_FORBIDDEN_CHARS = re.compile(r'[\\/:*?"<>|]')
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class SavedImageMetadata:
    domain: str
    owner_type: str | None
    owner_id: int | None
    original_file_name: str
    stored_file_name: str
    relative_path: str
    file_url: str
    file_ext: str
    mime_type: str | None
    file_size: int
    width: int | None
    height: int | None
    sort_order: int
    description: str | None


class ImageFileService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def sanitize_base_filename(original_filename: str) -> str:
        raw_name = Path(str(original_filename or "")).name
        base = Path(raw_name).stem
        normalized = unicodedata.normalize("NFKC", base)
        normalized = CONTROL_CHARS.sub("", normalized)
        normalized = WINDOWS_FORBIDDEN_CHARS.sub("_", normalized)
        normalized = re.sub(r"\s+", "_", normalized.strip())
        normalized = re.sub(r"_+", "_", normalized).strip("._ ")
        if not normalized:
            normalized = "image"
        return normalized[:80].rstrip("._ ") or "image"

    @staticmethod
    def get_domain_folder(domain: str) -> str:
        normalized = str(domain or "").strip()
        folder = DOMAIN_FOLDERS.get(normalized)
        if not folder:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unsupported image domain: {domain}")
        return folder

    @classmethod
    def ensure_year_month_dir(cls, domain: str, date: datetime) -> Path:
        folder = cls.get_domain_folder(domain)
        target = PROJECT_ROOT / "data" / folder / date.strftime("%Y") / date.strftime("%m")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def generate_sequence_filename(self, domain: str, original_filename: str, date: datetime) -> str:
        safe_base = self.sanitize_base_filename(original_filename)
        ext = Path(str(original_filename or "")).suffix.lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="jpg, jpeg, png, gif, webp files only")

        stamp = date.strftime("%Y%m%d")
        target_dir = self.ensure_year_month_dir(domain, date)
        next_seq = self._next_sequence(domain, stamp, target_dir)
        while next_seq <= 999:
            stored_file_name = f"{safe_base}_{stamp}{next_seq:03d}{ext}"
            if not (target_dir / stored_file_name).exists():
                return stored_file_name
            next_seq += 1
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="daily image sequence is exhausted")

    def save_uploaded_image(
        self,
        *,
        domain: str,
        original_filename: str,
        content_type: str | None,
        file_bytes: bytes,
        owner_type: str | None = None,
        owner_id: int | None = None,
        description: str | None = None,
        sort_order: int = 0,
    ) -> dict[str, object]:
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image file is required")
        if len(file_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image file must be 10MB or smaller")
        if content_type and content_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported image mime type")

        now_dt = datetime.now(ZoneInfo("Asia/Seoul"))
        safe_original = Path(str(original_filename or "image.png")).name or "image.png"
        stored_file_name = self.generate_sequence_filename(domain, safe_original, now_dt)
        target_dir = self.ensure_year_month_dir(domain, now_dt)
        save_path = target_dir / stored_file_name
        file_ext = save_path.suffix.lower().lstrip(".")
        mime_type = content_type or mimetypes.guess_type(stored_file_name)[0] or "application/octet-stream"
        if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported image mime type")

        relative_path = save_path.relative_to(PROJECT_ROOT).as_posix()
        file_url = "/" + quote(relative_path.replace("data/", "static/", 1), safe="/")
        metadata = SavedImageMetadata(
            domain=str(domain).strip(),
            owner_type=self._normalize_optional(owner_type),
            owner_id=owner_id,
            original_file_name=safe_original,
            stored_file_name=stored_file_name,
            relative_path=relative_path,
            file_url=file_url,
            file_ext=file_ext,
            mime_type=mime_type,
            file_size=len(file_bytes),
            width=None,
            height=None,
            sort_order=int(sort_order or 0),
            description=self._normalize_optional(description),
        )

        try:
            save_path.write_bytes(file_bytes)
            image_id = self._insert_metadata(metadata)
        except Exception:
            if save_path.exists():
                try:
                    save_path.unlink()
                except OSError:
                    pass
            raise
        return self.get_image(image_id)

    def list_images(
        self,
        *,
        domain: str | None = None,
        owner_type: str | None = None,
        owner_id: int | None = None,
    ) -> dict[str, object]:
        conditions = ["is_active = 1"]
        params: dict[str, object] = {}
        if domain:
            conditions.append("domain = :domain")
            params["domain"] = domain
        if owner_type:
            conditions.append("owner_type = :owner_type")
            params["owner_type"] = owner_type
        if owner_id is not None:
            conditions.append("owner_id = :owner_id")
            params["owner_id"] = owner_id
        where_sql = " AND ".join(conditions)
        rows = self.db.execute(
            text(f"""
                SELECT *
                FROM app_images
                WHERE {where_sql}
                ORDER BY sort_order ASC, id DESC
            """),
            params,
        ).mappings().all()
        items = [self._row_to_response(dict(row)) for row in rows]
        return {"items": items, "total_count": len(items)}

    def get_image(self, image_id: int) -> dict[str, object]:
        row = self.db.execute(text("SELECT * FROM app_images WHERE id = :image_id"), {"image_id": image_id}).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image metadata not found")
        return self._row_to_response(dict(row))

    def delete_image(self, image_id: int) -> dict[str, object]:
        row = self.db.execute(text("SELECT * FROM app_images WHERE id = :image_id"), {"image_id": image_id}).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image metadata not found")
        deleted, missing = self.delete_physical_file(str(row["relative_path"]))
        self.db.execute(text("DELETE FROM app_images WHERE id = :image_id"), {"image_id": image_id})
        self.db.commit()
        return {"success": True, "image_id": image_id, "file_deleted": deleted, "file_missing": missing}

    def delete_physical_file(self, file_path: str) -> tuple[bool, bool]:
        try:
            target = (PROJECT_ROOT / str(file_path)).resolve()
            data_root = (PROJECT_ROOT / "data").resolve()
            if not str(target).startswith(str(data_root)):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image path is outside data directory")
            if not target.exists():
                return False, True
            if not target.is_file():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image path is not a file")
            target.unlink()
            return True, False
        except HTTPException:
            raise
        except OSError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"failed to delete image file: {exc}") from exc

    def _next_sequence(self, domain: str, stamp: str, target_dir: Path) -> int:
        pattern = re.compile(rf"_{re.escape(stamp)}(\d{{3}})\.[^.]+$")
        max_seq = 0
        rows = self.db.execute(
            text("SELECT stored_file_name FROM app_images WHERE domain = :domain AND stored_file_name LIKE :pattern"),
            {"domain": domain, "pattern": f"%_{stamp}___.%"},
        ).fetchall()
        for row in rows:
            match = pattern.search(str(row[0] or ""))
            if match:
                max_seq = max(max_seq, int(match.group(1)))
        if target_dir.exists():
            for path in target_dir.iterdir():
                if not path.is_file():
                    continue
                match = pattern.search(path.name)
                if match:
                    max_seq = max(max_seq, int(match.group(1)))
        return max_seq + 1

    def _insert_metadata(self, metadata: SavedImageMetadata) -> int:
        now = now_kst()
        result = self.db.execute(
            text("""
                INSERT INTO app_images (
                    domain, owner_type, owner_id, original_file_name, stored_file_name,
                    relative_path, file_url, file_ext, mime_type, file_size, width, height,
                    sort_order, description, is_active, created_at, updated_at
                )
                VALUES (
                    :domain, :owner_type, :owner_id, :original_file_name, :stored_file_name,
                    :relative_path, :file_url, :file_ext, :mime_type, :file_size, :width, :height,
                    :sort_order, :description, 1, :created_at, :updated_at
                )
            """),
            {
                **metadata.__dict__,
                "created_at": now,
                "updated_at": now,
            },
        )
        self.db.commit()
        return int(result.lastrowid)

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _row_to_response(row: dict[str, object]) -> dict[str, object]:
        return {
            "id": int(row["id"]),
            "domain": str(row["domain"]),
            "owner_type": row.get("owner_type"),
            "owner_id": row.get("owner_id"),
            "original_file_name": str(row["original_file_name"]),
            "stored_file_name": str(row["stored_file_name"]),
            "relative_path": str(row["relative_path"]),
            "file_url": str(row["file_url"]),
            "file_ext": str(row["file_ext"]),
            "mime_type": row.get("mime_type"),
            "file_size": int(row["file_size"] or 0),
            "width": row.get("width"),
            "height": row.get("height"),
            "sort_order": int(row.get("sort_order") or 0),
            "description": row.get("description"),
            "is_active": int(row.get("is_active") or 0),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }
