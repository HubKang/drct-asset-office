import DOMPurify from "dompurify";

const htmlTagPattern = /<\/?[a-z][\s\S]*>/i;

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

export const sanitizeKmsHtml = (value: string) =>
  DOMPurify.sanitize(value || "", {
    ALLOWED_TAGS: [
      "p",
      "h1",
      "h2",
      "h3",
      "strong",
      "em",
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
    ],
    ALLOWED_ATTR: ["href", "src", "alt", "title", "target", "rel", "colspan", "rowspan", "width", "height", "style"],
    ADD_DATA_URI_TAGS: ["img"],
  });

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

export const toKmsDisplayHtml = (value: string) => bustLocalImageCache(linkifyTextUrls(toKmsEditableHtml(value)));

export const toKmsPlainText = (value: string) => {
  if (!value) return "";
  const html = toKmsDisplayHtml(value);
  if (typeof document === "undefined") return html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  const element = document.createElement("div");
  element.innerHTML = html;
  return (element.textContent || element.innerText || "").replace(/\s+/g, " ").trim();
};
