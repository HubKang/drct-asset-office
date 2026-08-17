import DOMPurify from "dompurify";

const htmlTagPattern = /<\/?[a-z][\s\S]*>/i;

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

const allowedStyleProperties = new Set(["color", "background-color", "font-size", "text-align", "width", "height", "max-width"]);

const cleanStyleValue = (property: string, value: string) => {
  const normalized = value.trim();
  if (!normalized) return "";
  if (/expression\s*\(|url\s*\(|javascript:/i.test(normalized)) return "";
  if (property === "text-align" && !/^(left|center|right)$/i.test(normalized)) return "";
  if ((property === "width" || property === "height" || property === "max-width" || property === "font-size") && !/^\d+(\.\d+)?(px|%|em|rem)$/i.test(normalized)) return "";
  if ((property === "color" || property === "background-color") && !/^(#[0-9a-f]{3,8}|rgb\([^)]+\)|rgba\([^)]+\)|[a-z]+)$/i.test(normalized)) return "";
  return normalized;
};

const filterAllowedStyles = (html: string) => {
  if (!html || typeof document === "undefined") return html;
  const container = document.createElement("div");
  container.innerHTML = html;
  container.querySelectorAll<HTMLElement>("[style]").forEach((element) => {
    const nextStyles: string[] = [];
    element.getAttribute("style")?.split(";").forEach((rule) => {
      const [rawProperty, ...rawValue] = rule.split(":");
      const property = rawProperty?.trim().toLowerCase();
      if (!property || !allowedStyleProperties.has(property)) return;
      const value = cleanStyleValue(property, rawValue.join(":"));
      if (value) nextStyles.push(`${property}: ${value}`);
    });
    if (nextStyles.length) element.setAttribute("style", nextStyles.join("; "));
    else element.removeAttribute("style");
  });
  return container.innerHTML;
};

export const sanitizeKmsHtml = (value: string) =>
  filterAllowedStyles(
    DOMPurify.sanitize(value || "", {
      ALLOWED_TAGS: [
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "ul",
        "ol",
        "li",
        "blockquote",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "a",
        "img",
        "br",
        "span",
        "div",
      ],
      ALLOWED_ATTR: ["href", "src", "alt", "title", "target", "rel", "colspan", "rowspan", "width", "height", "style", "data-kms-width"],
      ADD_DATA_URI_TAGS: ["img"],
      FORBID_TAGS: ["script", "iframe", "object", "embed"],
      FORBID_ATTR: ["onerror", "onclick", "onload", "onmouseover"],
    }),
  );

export const toKmsEditableHtml = (value: string) => {
  if (!value) return "";
  if (htmlTagPattern.test(value)) return sanitizeKmsHtml(value);
  return escapeHtml(value).replace(/\r?\n/g, "<br>");
};

const linkifyTextUrls = (html: string) => {
  if (!html || typeof document === "undefined") return html;
  const container = document.createElement("div");
  container.innerHTML = html;
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const textNodes: Text[] = [];
  let currentNode = walker.nextNode();
  while (currentNode) {
    const parent = currentNode.parentElement;
    if (parent && !parent.closest("a")) textNodes.push(currentNode as Text);
    currentNode = walker.nextNode();
  }

  const urlPattern = /(https?:\/\/[^\s<]+|www\.[^\s<]+)/g;
  textNodes.forEach((node) => {
    const text = node.nodeValue || "";
    if (!urlPattern.test(text)) return;
    urlPattern.lastIndex = 0;
    const fragment = document.createDocumentFragment();
    let lastIndex = 0;
    let match = urlPattern.exec(text);
    while (match) {
      const matchedUrl = match[0];
      const trailing = matchedUrl.match(/[),.;:!?]+$/)?.[0] || "";
      const cleanUrl = trailing ? matchedUrl.slice(0, -trailing.length) : matchedUrl;
      fragment.append(document.createTextNode(text.slice(lastIndex, match.index)));
      const anchor = document.createElement("a");
      anchor.href = cleanUrl.startsWith("www.") ? `https://${cleanUrl}` : cleanUrl;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.textContent = cleanUrl;
      fragment.append(anchor);
      if (trailing) fragment.append(document.createTextNode(trailing));
      lastIndex = match.index + matchedUrl.length;
      match = urlPattern.exec(text);
    }
    fragment.append(document.createTextNode(text.slice(lastIndex)));
    node.replaceWith(fragment);
  });
  return container.innerHTML;
};

const preserveTrailingParagraphBreaks = (html: string) => {
  if (!html || typeof document === "undefined") return html;
  const container = document.createElement("div");
  container.innerHTML = html;
  container.querySelectorAll("p").forEach((paragraph) => {
    let lastNode = paragraph.lastChild;
    while (lastNode?.nodeType === Node.TEXT_NODE && !(lastNode.textContent || "").trim()) lastNode = lastNode.previousSibling;
    if (!(lastNode instanceof HTMLBRElement)) return;
    const spacer = document.createElement("span");
    spacer.className = "kms-display-trailing-break";
    spacer.setAttribute("aria-hidden", "true");
    spacer.textContent = "\u00a0";
    lastNode.after(spacer);
  });
  return container.innerHTML;
};


const bustLocalImageCache = (html: string) => {
  if (!html || typeof document === "undefined") return html;
  const container = document.createElement("div");
  container.innerHTML = html;
  container.querySelectorAll("img").forEach((image) => {
    const src = image.getAttribute("src") || "";
    if (!src.includes("/kms/local-image")) return;
    try {
      const url = new URL(src, window.location.origin);
      url.searchParams.set("_kms_cache_bust", String(Date.now()));
      image.setAttribute("src", url.toString());
    } catch {
      const separator = src.includes("?") ? "&" : "?";
      image.setAttribute("src", `${src}${separator}_kms_cache_bust=${Date.now()}`);
    }
  });
  return container.innerHTML;
};

export const toKmsDisplayHtml = (value: string) =>
  bustLocalImageCache(preserveTrailingParagraphBreaks(linkifyTextUrls(toKmsEditableHtml(value))));

export const toKmsPlainText = (value: string) => {
  if (!value) return "";
  const html = toKmsDisplayHtml(value);
  if (typeof document === "undefined") return html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  const element = document.createElement("div");
  element.innerHTML = html;
  return (element.textContent || element.innerText || "").replace(/\s+/g, " ").trim();
};

export const extractKmsImageSources = (value: string) => {
  if (!value || typeof document === "undefined") return [] as string[];
  const container = document.createElement("div");
  container.innerHTML = value;
  return Array.from(container.querySelectorAll("img"))
    .map((image) => image.getAttribute("src")?.trim() || "")
    .filter(Boolean);
};
