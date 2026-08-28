from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import requests


class TelegramArticleService:
    """Fetches article text transiently with strict network and size boundaries."""

    TIMEOUT = (4, 8)
    MAX_BYTES = 1_000_000
    MAX_REDIRECTS = 4
    MIN_TEXT_LENGTH = 200
    USER_AGENT = "Mozilla/5.0 (compatible; DrCT-ArticleBriefing/1.0)"

    def fetch_text(self, source_url: str) -> str | None:
        current = source_url.strip()
        session = requests.Session()
        try:
            for _ in range(self.MAX_REDIRECTS + 1):
                self.validate_public_url(current)
                response = session.get(
                    current,
                    headers={"User-Agent": self.USER_AGENT, "Accept": "text/html,text/plain;q=0.9"},
                    timeout=self.TIMEOUT,
                    allow_redirects=False,
                    stream=True,
                )
                try:
                    if response.is_redirect or response.is_permanent_redirect:
                        location = response.headers.get("location")
                        if not location:
                            return None
                        current = urljoin(current, location)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if "text/html" not in content_type and "text/plain" not in content_type:
                        return None
                    declared = response.headers.get("content-length")
                    if declared and int(declared) > self.MAX_BYTES:
                        return None
                    payload = self._read_limited(response)
                    if payload is None:
                        return None
                    encoding = response.encoding or response.apparent_encoding or "utf-8"
                    text = self.extract_article_text(payload.decode(encoding, errors="replace"))
                    return text if len(text) >= self.MIN_TEXT_LENGTH else None
                finally:
                    response.close()
            return None
        except (OSError, ValueError, requests.RequestException):
            return None
        finally:
            session.close()

    @classmethod
    def validate_public_url(cls, value: str) -> None:
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise ValueError("unsupported article URL")
        if parts.username or parts.password:
            raise ValueError("credentials are not allowed in article URL")
        port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
        for address in cls._resolve_ips(parts.hostname, port):
            ip = ipaddress.ip_address(address)
            if getattr(ip, "ipv4_mapped", None):
                ip = ip.ipv4_mapped
            if not ip.is_global:
                raise ValueError("private or non-public article host")

    @staticmethod
    def _resolve_ips(hostname: str, port: int) -> set[str]:
        return {row[4][0] for row in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)}

    def _read_limited(self, response: requests.Response) -> bytes | None:
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=32_768):
            if not chunk:
                continue
            size += len(chunk)
            if size > self.MAX_BYTES:
                return None
            chunks.append(chunk)
        return b"".join(chunks)

    @classmethod
    def extract_article_text(cls, html_text: str) -> str:
        """Extract only an explicitly identified article body.

        A page-wide fallback is deliberately forbidden. News pages commonly contain
        long recommendation/headline lists; treating the longest generic ``content``
        container as the article can mix unrelated stories into an LLM prompt.
        """
        candidates = cls._json_ld_article_bodies(html_text)
        parser = _ArticleBodyParser()
        try:
            parser.feed(html_text)
            parser.close()
            candidates.extend(parser.explicit_candidates)
            if not candidates:
                candidates.extend(parser.article_candidates)
        except Exception:
            # Malformed provider HTML must fail closed instead of becoming an LLM prompt.
            pass

        texts = [cls._plain_text(candidate) for candidate in candidates]
        texts = [value for value in texts if len(value) >= cls.MIN_TEXT_LENGTH]
        return max(texts, key=len)[:15_000] if texts else ""

    @classmethod
    def _json_ld_article_bodies(cls, html_text: str) -> list[str]:
        bodies: list[str] = []
        scripts = re.findall(
            r"(?is)<script\b[^>]*type\s*=\s*['\"]application/ld\+json['\"][^>]*>(.*?)</script>",
            html_text,
        )

        def visit(value: object) -> None:
            if isinstance(value, dict):
                body = value.get("articleBody")
                if isinstance(body, str) and body.strip():
                    bodies.append(body)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        for script in scripts:
            try:
                visit(json.loads(html.unescape(script).strip()))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        return bodies

    @staticmethod
    def _plain_text(value: str) -> str:
        value = re.sub(r"(?i)<br\s*/?>|</(?:p|div|li|h[1-6]|blockquote)\s*>", "\n", value)
        value = re.sub(r"<[^>]+>", " ", value)
        lines = [re.sub(r"\s+", " ", line).strip() for line in html.unescape(value).splitlines()]
        blocked = ("무단전재", "재배포 금지", "copyright", "로그인", "구독", "관련기사", "많이 본 뉴스")
        return "\n".join(
            line for line in lines if line and not any(term in line.lower() for term in blocked)
        )

    @staticmethod
    def _html_to_text(value: str) -> str:
        text = re.sub(r"(?i)<br\s*/?>|</(?:p|div|li|h[1-6])\s*>", "\n", value)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        blocked = ("무단전재", "재배포 금지", "copyright", "로그인", "구독", "관련기사", "많이 본 뉴스")
        return "\n".join(line for line in lines if len(line) >= 20 and not any(term in line.lower() for term in blocked))


class _ArticleBodyParser(HTMLParser):
    """Captures exact article-body containers while respecting nested markup."""

    BODY_NAMES = {
        "articlebody", "article-body", "article_body", "article-content", "article_content",
        "newsbody", "news-body", "news_body",
        "dic_area", "newsct_article", "_article_content", "view_content", "viewcontent",
    }
    BLOCK_TAGS = {"br", "p", "div", "section", "li", "h1", "h2", "h3", "h4", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._active: list[dict[str, object]] = []
        self.explicit_candidates: list[str] = []
        self.article_candidates: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        for capture in self._active:
            if capture["tag"] == normalized_tag:
                capture["nesting"] = int(capture["nesting"]) + 1
        attr_map = {key.lower(): (value or "") for key, value in attrs}
        names = {token.lower() for token in re.split(r"\s+", f"{attr_map.get('id', '')} {attr_map.get('class', '')}") if token}
        itemprop = attr_map.get("itemprop", "").lower()
        explicit = itemprop == "articlebody" or bool(names.intersection(self.BODY_NAMES))
        if normalized_tag == "article" or explicit:
            self._active.append({"tag": normalized_tag, "nesting": 1, "chunks": [], "explicit": explicit})
        if normalized_tag in self.BLOCK_TAGS:
            self._append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self._append("\n")

    def handle_data(self, data: str) -> None:
        self._append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in self.BLOCK_TAGS:
            self._append("\n")
        completed: list[dict[str, object]] = []
        for capture in self._active:
            if capture["tag"] == normalized_tag:
                capture["nesting"] = int(capture["nesting"]) - 1
                if capture["nesting"] == 0:
                    completed.append(capture)
        for capture in completed:
            target = self.explicit_candidates if capture["explicit"] else self.article_candidates
            target.append("".join(capture["chunks"]))
            self._active.remove(capture)

    def _append(self, value: str) -> None:
        for capture in self._active:
            capture["chunks"].append(value)
