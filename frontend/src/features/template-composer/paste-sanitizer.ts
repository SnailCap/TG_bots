import { escapeTelegramText, normalizeTelegramHtml } from "./serializer";
import {
  FORMAT_KIND_BY_ALIAS,
  TELEGRAM_DATE_TIME_FORMAT,
  isSafeWebUrl,
  parseTelegramMentionHref,
} from "./telegram-formatting";

const BLOCK_ELEMENTS = new Set(["address", "article", "div", "footer", "header", "li", "main", "p", "section"]);

export function sanitizePastedHtml(html: string): string {
  if (!html.trim()) return "";
  const parsed = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
  return normalizeTelegramHtml(sanitizeChildren(parsed.body).replace(/\n{3,}/g, "\n\n").replace(/\n+$/, ""));
}

function sanitizeChildren(parent: ParentNode): string {
  return Array.from(parent.childNodes).map(sanitizeNode).join("");
}

function sanitizeNode(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return escapeTelegramText(node.textContent ?? "");
  if (!(node instanceof HTMLElement)) return "";
  const tag = node.tagName.toLowerCase();
  const content = sanitizeChildren(node);

  if (tag === "br") return "\n";
  if (BLOCK_ELEMENTS.has(tag)) return `${content}\n`;
  if (tag === "span") {
    if (node.classList.contains("tg-spoiler")) return `<tg-spoiler>${content}</tg-spoiler>`;
    return wrapConvertibleInlineStyles(node, content);
  }
  if (tag === "a") {
    const href = node.getAttribute("href") ?? "";
    const userId = parseTelegramMentionHref(href);
    if (userId) return `<a href="tg://user?id=${userId}">${content}</a>`;
    return isSafeWebUrl(href) ? `<a href="${escapeAttribute(href)}">${content}</a>` : content;
  }
  if (tag === "blockquote") return node.hasAttribute("expandable")
    ? `<blockquote expandable>${content}</blockquote>`
    : `<blockquote>${content}</blockquote>`;
  if (tag === "pre") {
    const code = node.children.length === 1 && node.children[0].tagName.toLowerCase() === "code"
      ? node.children[0] as HTMLElement
      : null;
    const language = code?.className.match(/(?:^|\s)language-([A-Za-z0-9_+#.-]+)(?:\s|$)/)?.[1];
    const codeContent = code ? sanitizeChildren(code) : content;
    return language
      ? `<pre><code class="language-${escapeAttribute(language)}">${stripFormatting(codeContent)}</code></pre>`
      : `<pre>${stripFormatting(codeContent)}</pre>`;
  }
  if (tag === "tg-emoji") {
    const emojiId = node.getAttribute("emoji-id") ?? "";
    return /^\d+$/.test(emojiId) && node.textContent
      ? `<tg-emoji emoji-id="${emojiId}">${escapeTelegramText(node.textContent)}</tg-emoji>`
      : content;
  }
  if (tag === "tg-time") {
    const unix = node.getAttribute("unix") ?? "";
    const format = node.getAttribute("format") ?? "";
    return /^\d+$/.test(unix) && TELEGRAM_DATE_TIME_FORMAT.test(format)
      ? `<tg-time unix="${unix}"${format ? ` format="${format}"` : ""}>${escapeTelegramText(node.textContent ?? "")}</tg-time>`
      : content;
  }

  const format = FORMAT_KIND_BY_ALIAS.get(tag);
  if (!format) return content;
  if (format === "inline-code") return `<code>${stripFormatting(content)}</code>`;
  const canonical = format === "bold" ? "b"
    : format === "italic" ? "i"
      : format === "underline" ? "u"
        : format === "strikethrough" ? "s"
          : format === "spoiler" ? "tg-spoiler"
            : null;
  return canonical ? `<${canonical}>${content}</${canonical}>` : content;
}

function wrapConvertibleInlineStyles(element: HTMLElement, content: string): string {
  const style = element.style;
  let result = content;
  if (style.textDecorationLine.includes("line-through")) result = `<s>${result}</s>`;
  if (style.textDecorationLine.includes("underline")) result = `<u>${result}</u>`;
  if (style.fontStyle === "italic") result = `<i>${result}</i>`;
  const numericWeight = Number(style.fontWeight);
  if (style.fontWeight === "bold" || (Number.isFinite(numericWeight) && numericWeight >= 600)) result = `<b>${result}</b>`;
  return result;
}

function stripFormatting(value: string): string {
  const parsed = new DOMParser().parseFromString(`<body>${value}</body>`, "text/html");
  return escapeTelegramText(parsed.body.textContent ?? "");
}

function escapeAttribute(value: string): string {
  return escapeTelegramText(value).replaceAll('"', "&quot;");
}
