from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import html
import ipaddress
import logging
import re
import socket
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import requests


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArticleExtractionResult:
    """Transient extraction metadata. Only ``summary`` is persisted elsewhere."""

    success: bool
    text: str = ""
    method: str | None = None
    title_similarity: float = 0.0
    char_count: int = 0
    paragraph_count: int = 0
    failure_reason: str | None = None


@dataclass
class _DomNode:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    parent: _DomNode | None = None
    children: list[_DomNode | str] = field(default_factory=list)

    def descendants(self, include_self: bool = False):  # type: ignore[no-untyped-def]
        if include_self:
            yield self
        for child in self.children:
            if isinstance(child, _DomNode):
                yield child
                yield from child.descendants()

    def text_content(self) -> str:
        return "".join(child.text_content() if isinstance(child, _DomNode) else child for child in self.children)


class _DomParser(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _DomNode("document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        node = _DomNode(normalized, {key.lower(): value or "" for key, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if normalized not in self.VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in self.VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == normalized:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


class TelegramArticleService:
    """Safely fetches and validates one article without retaining provider payloads."""

    TIMEOUT = (4, 8)
    MAX_BYTES = 1_000_000
    MAX_REDIRECTS = 4
    USER_AGENT = "Mozilla/5.0 (compatible; DrCT-ArticleBriefing/1.0)"

    ARTICLE_TITLE_MATCH_THRESHOLD = 0.84
    META_TITLE_MATCH_THRESHOLD = 0.60
    MAX_ARTICLE_ANCESTOR_DEPTH = 5
    MIN_ARTICLE_BODY_CHARS = 300
    MIN_ARTICLE_PARAGRAPHS = 2
    MAX_ARTICLE_LINK_DENSITY = 0.32
    MIN_TITLE_BODY_RELEVANCE = 0.25
    MAX_TEXT_CHARS = 15_000

    TITLE_SEMANTIC_NAMES = {
        "headline", "article-title", "article_title", "news-title", "news_title",
        "entry-title", "entry_title", "post-title", "post_title",
    }
    EXCLUDED_TAGS = {"script", "style", "noscript", "nav", "footer", "header", "aside", "form", "button", "iframe", "svg"}
    STOP_PHRASES = (
        "관련기사", "관련 기사", "추천기사", "추천 기사", "인기기사", "인기 기사",
        "많이 본 뉴스", "많이 본 기사", "함께 본 뉴스", "기자의 다른 기사",
        "이 기자의 다른 기사", "이 시각 주요뉴스", "주요 뉴스", "무단전재",
        "재배포 금지", "copyright", "저작권자",
    )
    RELATED_NAMES = ("related", "recommend", "popular", "ranking", "more-news", "other-news", "relation_news")
    TITLE_TOKEN_STOPWORDS = {
        "단독", "속보", "특징주", "종합", "포토", "영상", "인터뷰", "기자", "뉴스",
        "오늘", "내일", "관련", "전망", "분석", "이유", "논란", "공개",
    }

    def fetch_article(self, source_url: str, article_title: str, stock_name: str | None = None) -> ArticleExtractionResult:
        current = (source_url or "").strip()
        if not current or not (article_title or "").strip():
            return self._failure("SOURCE_INPUT_MISSING")
        session = requests.Session()
        try:
            for _ in range(self.MAX_REDIRECTS + 1):
                self.validate_public_url(current)
                response = session.get(
                    current,
                    headers={"User-Agent": self.USER_AGENT, "Accept": "text/html;q=1.0,text/plain;q=0.8"},
                    timeout=self.TIMEOUT,
                    allow_redirects=False,
                    stream=True,
                )
                try:
                    if response.is_redirect or response.is_permanent_redirect:
                        location = response.headers.get("location")
                        if not location:
                            return self._failure("REDIRECT_LOCATION_MISSING")
                        current = urljoin(current, location)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if "text/html" not in content_type:
                        return self._failure("UNSUPPORTED_CONTENT_TYPE")
                    declared = response.headers.get("content-length")
                    if declared and int(declared) > self.MAX_BYTES:
                        return self._failure("RESPONSE_TOO_LARGE")
                    payload = self._read_limited(response)
                    if payload is None:
                        return self._failure("RESPONSE_TOO_LARGE")
                    encoding = response.encoding or response.apparent_encoding or "utf-8"
                    result = self.extract_article(payload.decode(encoding, errors="replace"), article_title, stock_name)
                    logger.info(
                        "Article extraction url=%s method=%s chars=%d paragraphs=%d title_similarity=%.3f failure=%s",
                        current, result.method, result.char_count, result.paragraph_count,
                        result.title_similarity, result.failure_reason,
                    )
                    return result
                finally:
                    response.close()
            return self._failure("TOO_MANY_REDIRECTS")
        except (OSError, ValueError, requests.RequestException) as exc:
            logger.info("Article fetch failed url=%s reason=%s", current, type(exc).__name__)
            return self._failure("URL_FETCH_FAILED")
        finally:
            session.close()

    def fetch_text(self, source_url: str, article_title: str | None = None, stock_name: str | None = None) -> str | None:
        """Compatibility wrapper; a title is mandatory so extraction cannot fall back."""
        if not article_title:
            return None
        result = self.fetch_article(source_url, article_title, stock_name)
        return result.text if result.success else None

    @classmethod
    def extract_article(cls, html_text: str, article_title: str, stock_name: str | None = None) -> ArticleExtractionResult:
        parser = _DomParser()
        try:
            parser.feed(html_text)
            parser.close()
        except Exception:
            return cls._failure("HTML_PARSE_FAILED")

        title_match = cls._find_title_anchor(parser.root, article_title)
        if not title_match:
            return cls._failure("TITLE_ANCHOR_NOT_FOUND")
        anchor, title_similarity = title_match

        meta_titles = cls._metadata_titles(parser.root)
        if meta_titles and max(cls.title_similarity(article_title, value) for value in meta_titles) < cls.META_TITLE_MATCH_THRESHOLD:
            return cls._failure("META_TITLE_MISMATCH", title_similarity=title_similarity)

        last_failure = "ARTICLE_CONTAINER_NOT_FOUND"
        ancestor: _DomNode | None = anchor.parent
        for _depth in range(cls.MAX_ARTICLE_ANCESTOR_DEPTH + 1):
            if ancestor is None or ancestor.tag in {"html", "body", "main", "document"}:
                break
            semantic_bodies = [
                node for node in ancestor.descendants(include_self=True)
                if node.attrs.get("itemprop", "").lower() == "articlebody"
            ]
            for body in semantic_bodies:
                result = cls._validate_candidate(body, anchor, article_title, stock_name, title_similarity, "TITLE_ANCHOR_ARTICLE_BODY")
                if result.success:
                    return result
                last_failure = result.failure_reason or last_failure

            if ancestor.tag == "article":
                result = cls._validate_candidate(ancestor, anchor, article_title, stock_name, title_similarity, "TITLE_ANCHOR_ARTICLE")
                if result.success:
                    return result
                last_failure = result.failure_reason or last_failure

            result = cls._validate_candidate(ancestor, anchor, article_title, stock_name, title_similarity, "TITLE_ANCHOR_CONTAINER")
            if result.success:
                return result
            last_failure = result.failure_reason or last_failure
            ancestor = ancestor.parent
        return cls._failure(last_failure, title_similarity=title_similarity)

    @classmethod
    def extract_article_text(cls, html_text: str, article_title: str | None = None, stock_name: str | None = None) -> str:
        if not article_title:
            return ""
        result = cls.extract_article(html_text, article_title, stock_name)
        return result.text if result.success else ""

    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", html.unescape(value or "")).lower()
        normalized = normalized.replace("…", "...").replace("⋯", "...")
        normalized = re.sub(r"[‘’‚‛“”„‟'\"`´]+", " ", normalized)
        normalized = re.sub(r"\.{2,}", " ", normalized)
        normalized = re.sub(r"[^0-9a-z가-힣_]+", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    @classmethod
    def title_similarity(cls, left: str, right: str) -> float:
        first, second = cls.normalize_title(left), cls.normalize_title(right)
        if not first or not second:
            return 0.0
        sequence = SequenceMatcher(None, first, second).ratio()
        first_tokens, second_tokens = cls._title_tokens(first), cls._title_tokens(second)
        common = first_tokens.intersection(second_tokens)
        # A one-word heading such as a company name must not become an article
        # anchor merely because that token also appears in the actual headline.
        overlap = (
            len(common) / max(1, min(len(first_tokens), len(second_tokens)))
            if len(common) >= 2
            else 0.0
        )
        containment = 1.0 if (first in second or second in first) and len(min(first, second, key=len)) >= 12 else 0.0
        return max(sequence, overlap, containment)

    @classmethod
    def _find_title_anchor(cls, root: _DomNode, article_title: str) -> tuple[_DomNode, float] | None:
        matches: list[tuple[float, _DomNode]] = []
        for node in root.descendants():
            if not cls._is_title_candidate(node):
                continue
            candidate = cls._clean_space(node.text_content())
            if len(candidate) < 8:
                continue
            score = cls.title_similarity(article_title, candidate)
            if score >= cls.ARTICLE_TITLE_MATCH_THRESHOLD:
                matches.append((score, node))
        if not matches:
            return None
        score, node = max(matches, key=lambda item: item[0])
        return node, score

    @classmethod
    def _is_title_candidate(cls, node: _DomNode) -> bool:
        if node.tag in {"h1", "h2"} or node.attrs.get("itemprop", "").lower() == "headline":
            return True
        names = cls._semantic_names(node)
        if names.intersection(cls.TITLE_SEMANTIC_NAMES):
            return True
        # Some publishers use a div-based headline without h1/h2. Recognize
        # generic title/headline semantics; the strong similarity threshold still
        # prevents page and list-heading wrappers from becoming article anchors.
        return any(re.search(r"(?:^|[-_])(title|headline)(?:[-_]|$)", name) for name in names)

    @classmethod
    def _metadata_titles(cls, root: _DomNode) -> list[str]:
        values: list[str] = []
        for node in root.descendants():
            if node.tag != "meta":
                continue
            key = (node.attrs.get("property") or node.attrs.get("name") or "").lower()
            if key in {"og:title", "twitter:title"} and node.attrs.get("content"):
                values.append(node.attrs["content"])
        return values

    @classmethod
    def _validate_candidate(cls, candidate: _DomNode, anchor: _DomNode, article_title: str, stock_name: str | None, title_similarity: float, method: str) -> ArticleExtractionResult:
        text, paragraphs, link_density = cls._candidate_text(candidate, anchor)
        char_count, paragraph_count = len(text), len(paragraphs)
        if char_count < cls.MIN_ARTICLE_BODY_CHARS:
            return cls._failure("ARTICLE_BODY_TOO_SHORT", title_similarity, char_count, paragraph_count)
        if paragraph_count < cls.MIN_ARTICLE_PARAGRAPHS and char_count < 700:
            return cls._failure("ARTICLE_PARAGRAPHS_TOO_FEW", title_similarity, char_count, paragraph_count)
        if link_density > cls.MAX_ARTICLE_LINK_DENSITY:
            return cls._failure("ARTICLE_LINK_DENSITY_HIGH", title_similarity, char_count, paragraph_count)

        title_tokens = cls._title_tokens(cls.normalize_title(article_title))
        body_tokens = set(cls.normalize_title(text).split())
        common = title_tokens.intersection(body_tokens)
        relevance = len(common) / max(1, min(4, len(title_tokens)))
        stock_present = bool(stock_name and cls.normalize_title(stock_name) in cls.normalize_title(text))
        if relevance < cls.MIN_TITLE_BODY_RELEVANCE and not (stock_present and common):
            return cls._failure("TITLE_BODY_RELEVANCE_LOW", title_similarity, char_count, paragraph_count)
        return ArticleExtractionResult(
            success=True, text=text[: cls.MAX_TEXT_CHARS], method=method,
            title_similarity=title_similarity, char_count=min(char_count, cls.MAX_TEXT_CHARS),
            paragraph_count=paragraph_count,
        )

    @classmethod
    def _candidate_text(cls, candidate: _DomNode, anchor: _DomNode) -> tuple[str, list[str], float]:
        pieces: list[tuple[str, bool, bool]] = []
        stopped = False
        seen_anchor = not cls._contains_node(candidate, anchor)

        def walk(node: _DomNode, in_link: bool = False) -> None:
            nonlocal stopped, seen_anchor
            if stopped:
                return
            if node is anchor:
                seen_anchor = True
                return
            if node.tag in cls.EXCLUDED_TAGS:
                if cls._contains_node(node, anchor):
                    seen_anchor = True
                return
            names = " ".join(cls._semantic_names(node))
            if any(marker in names for marker in cls.RELATED_NAMES):
                if pieces:
                    stopped = True
                return
            node_text = cls._clean_space(node.text_content())
            if pieces and cls._starts_with_stop_phrase(node_text):
                stopped = True
                return
            linked = in_link or node.tag == "a"
            for child in node.children:
                if stopped:
                    return
                if isinstance(child, str):
                    if seen_anchor and child.strip():
                        pieces.append((child, linked, False))
                else:
                    walk(child, linked)
                    if seen_anchor and child.tag in {"br", "p", "div", "section", "li", "blockquote", "h3", "h4"}:
                        pieces.append(("\n", False, True))

        walk(candidate)
        raw_lines: list[str] = []
        buffer: list[str] = []
        total_chars = 0
        link_chars = 0
        for value, linked, is_break in pieces:
            if is_break:
                line = cls._clean_space(" ".join(buffer))
                if line:
                    raw_lines.append(line)
                buffer = []
                continue
            clean = cls._clean_space(value)
            if not clean:
                continue
            total_chars += len(clean)
            if linked:
                link_chars += len(clean)
            buffer.append(clean)
        final_line = cls._clean_space(" ".join(buffer))
        if final_line:
            raw_lines.append(final_line)

        paragraphs: list[str] = []
        for line in raw_lines:
            if cls._starts_with_stop_phrase(line):
                break
            if len(line) >= 20:
                paragraphs.append(line)
        return "\n".join(paragraphs), paragraphs, link_chars / max(1, total_chars)

    @staticmethod
    def _contains_node(container: _DomNode, target: _DomNode) -> bool:
        current: _DomNode | None = target
        while current is not None:
            if current is container:
                return True
            current = current.parent
        return False

    @classmethod
    def _starts_with_stop_phrase(cls, value: str) -> bool:
        normalized = cls._clean_space(value).lower()
        return any(normalized.startswith(phrase.lower()) for phrase in cls.STOP_PHRASES)

    @classmethod
    def _semantic_names(cls, node: _DomNode) -> set[str]:
        return {token.lower() for token in re.split(r"\s+", f"{node.attrs.get('id', '')} {node.attrs.get('class', '')}") if token}

    @classmethod
    def _title_tokens(cls, normalized_title: str) -> set[str]:
        return {token for token in normalized_title.split() if len(token) >= 2 and token not in cls.TITLE_TOKEN_STOPWORDS}

    @staticmethod
    def _clean_space(value: str) -> str:
        return re.sub(r"\s+", " ", html.unescape(value or "")).strip()

    @classmethod
    def _failure(cls, reason: str, title_similarity: float = 0.0, char_count: int = 0, paragraph_count: int = 0) -> ArticleExtractionResult:
        return ArticleExtractionResult(
            success=False, title_similarity=title_similarity, char_count=char_count,
            paragraph_count=paragraph_count, failure_reason=reason,
        )

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
