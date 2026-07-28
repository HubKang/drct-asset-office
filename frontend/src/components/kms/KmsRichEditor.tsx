import { useCallback, useEffect, useRef, useState, type ChangeEvent, type MouseEvent } from "react";
import { Extension, type Editor } from "@tiptap/core";
import Color from "@tiptap/extension-color";
import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { Table } from "@tiptap/extension-table";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import TableRow from "@tiptap/extension-table-row";
import { TextStyle } from "@tiptap/extension-text-style";
import Underline from "@tiptap/extension-underline";
import { EditorContent, useEditor } from "@tiptap/react";
import { TextSelection } from "@tiptap/pm/state";
import StarterKit from "@tiptap/starter-kit";
import { imageApiRepository } from "@/services/api/imageApiRepository";
import { appConfig } from "@/services/config/appConfig";
import type { AppImageDomain } from "@/types/image";
import { toKmsEditableHtml } from "@/utils/kmsRichContent";

type KmsRichEditorProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  resetKey?: string | number;
  selectLocalImage?: () => Promise<{ selected: boolean; path?: string | null; url?: string | null }>;
  imageUploadDomain?: AppImageDomain;
  ownerType?: string;
  ownerId?: number | string | null;
  enableImageUpload?: boolean;
};

const KmsImage = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      width: {
        default: null,
        parseHTML: (element) => element.getAttribute("width") || element.style.width || null,
        renderHTML: (attributes) => {
          if (!attributes.width) return {};
          return { width: attributes.width, style: `width: ${attributes.width};` };
        },
      },
      height: {
        default: null,
        parseHTML: (element) => element.getAttribute("height") || element.style.height || null,
        renderHTML: (attributes) => (attributes.height ? { height: attributes.height, style: `height: ${attributes.height};` } : {}),
      },
    };
  },
});

const KmsTextStyleAttributes = Extension.create({
  name: "kmsTextStyleAttributes",
  addGlobalAttributes() {
    return [
      {
        types: ["textStyle"],
        attributes: {
          fontSize: {
            default: null,
            parseHTML: (element) => element.style.fontSize || null,
            renderHTML: (attributes) => (attributes.fontSize ? { style: `font-size: ${attributes.fontSize}` } : {}),
          },
          backgroundColor: {
            default: null,
            parseHTML: (element) => element.style.backgroundColor || null,
            renderHTML: (attributes) => (attributes.backgroundColor ? { style: `background-color: ${attributes.backgroundColor}` } : {}),
          },
        },
      },
    ];
  },
});

const KmsTextAlign = Extension.create({
  name: "kmsTextAlign",
  addGlobalAttributes() {
    return [
      {
        types: ["heading", "paragraph"],
        attributes: {
          textAlign: {
            default: null,
            parseHTML: (element) => element.style.textAlign || null,
            renderHTML: (attributes) => (attributes.textAlign ? { style: `text-align: ${attributes.textAlign}` } : {}),
          },
        },
      },
    ];
  },
});

const fontSizeOptions = ["12px", "14px", "16px", "18px", "20px", "24px", "28px"];
const textColorOptions = ["#0f172a", "#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c"];
const backgroundColorOptions = ["transparent", "#fef3c7", "#dcfce7", "#dbeafe", "#fce7f3", "#fee2e2"];

function KmsRichEditor({
  value,
  onChange,
  placeholder = "Enter content",
  resetKey = "kms-editor",
  selectLocalImage,
  imageUploadDomain = "kms",
  ownerType = "kms_post",
  ownerId = null,
  enableImageUpload = true,
}: KmsRichEditorProps) {
  const lastAppliedResetKeyRef = useRef<string | number>(resetKey);
  const lastEmittedHtmlRef = useRef("");
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const [imageUploadError, setImageUploadError] = useState("");
  const [imageUploadMessage, setImageUploadMessage] = useState("");

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextStyle,
      KmsTextStyleAttributes,
      KmsTextAlign,
      Color,
      Link.configure({
        openOnClick: false,
        autolink: true,
        HTMLAttributes: {
          target: "_blank",
          rel: "noopener noreferrer",
        },
      }),
      KmsImage.configure({
        allowBase64: true,
        HTMLAttributes: {
          loading: "lazy",
        },
      }),
      Table.configure({
        resizable: true,
      }),
      TableRow,
      TableHeader,
      TableCell,
      Placeholder.configure({ placeholder }),
    ],
    content: toKmsEditableHtml(value),
    onUpdate: ({ editor: activeEditor }) => {
      const nextHtml = activeEditor.getHTML();
      lastEmittedHtmlRef.current = nextHtml;
      onChange(nextHtml);
    },
    editorProps: {
      attributes: {
        class: "kms-editor-content",
        "data-testid": "kms-rich-editor-content",
      },
      handleClick: (view, position, event) => {
        if (event.button !== 0 || event.detail !== 1 || event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) return false;
        const target = event.target instanceof HTMLElement ? event.target : null;
        if (target?.closest("a, img, table")) return false;
        const selection = TextSelection.near(view.state.doc.resolve(position));
        view.dispatch(view.state.tr.setSelection(selection));
        return true;
      },
    },
  });

  useEffect(() => {
    if (!editor) return;
    const nextContent = toKmsEditableHtml(value);
    const resetKeyChanged = lastAppliedResetKeyRef.current !== resetKey;
    if (!resetKeyChanged && value === lastEmittedHtmlRef.current) return;
    if (!resetKeyChanged && editor.isFocused) return;
    if (editor.getHTML() === nextContent) {
      lastAppliedResetKeyRef.current = resetKey;
      return;
    }
    editor.commands.setContent(nextContent, { emitUpdate: false });
    lastAppliedResetKeyRef.current = resetKey;
    lastEmittedHtmlRef.current = nextContent;
  }, [editor, resetKey, value]);

  const run = useCallback(
    (action: () => void) => {
      if (!editor) return;
      action();
    },
    [editor],
  );

  const keepSelection = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
  };

  const buttonClass = (active = false) => (active ? "kms-editor-button active" : "kms-editor-button");
  const isImageSelected = editor?.isActive("image") ?? false;
  const isTableSelected = editor?.isActive("table") ?? false;
  const activeImageWidth = (editor?.getAttributes("image").width as string | null | undefined) || "50%";
  const activeImageWidthValue = Math.max(0, Math.min(100, Number.parseInt(activeImageWidth, 10) || 0));

  const setLink = () => {
    if (!editor) return;
    const previousUrl = editor.getAttributes("link").href as string | undefined;
    const url = window.prompt("Link URL", previousUrl || "https://");
    if (url === null) return;
    if (!url.trim()) {
      run(() => editor.chain().focus(undefined, { scrollIntoView: false }).extendMarkRange("link").unsetLink().run());
      return;
    }
    run(() => editor.chain().focus(undefined, { scrollIntoView: false }).extendMarkRange("link").setLink({ href: url.trim() }).run());
  };

  const insertImageUrl = () => {
    if (!editor) return;
    const url = window.prompt("이미지 URL", "https://");
    if (url === null) return;
    const trimmedUrl = url.trim();
    if (!trimmedUrl) return;
    run(() =>
      editor
        .chain()
        .focus()
        .setImage({ src: trimmedUrl, alt: trimmedUrl.split("/").pop() || "image", width: "50%" } as never)
        .createParagraphNear()
        .run(),
    );
    setImageUploadError("");
    setImageUploadMessage("이미지 URL을 본문에 삽입했습니다.");
  };

  const normalizeOwnerId = () => {
    if (ownerId === null || ownerId === undefined || ownerId === "") return undefined;
    const numericOwnerId = typeof ownerId === "number" ? ownerId : Number(ownerId);
    return Number.isFinite(numericOwnerId) ? numericOwnerId : undefined;
  };

  const toRenderableImageUrl = (fileUrl: string) => {
    if (/^https?:\/\//i.test(fileUrl)) return fileUrl;
    const normalized = fileUrl.startsWith("/") ? fileUrl : `/${fileUrl}`;
    return `${appConfig.apiBaseUrl}${normalized}`;
  };

  const uploadEditorImage = async (file: File) => {
    if (!editor || !enableImageUpload || !imageUploadDomain) return;
    if (!file.type.startsWith("image/")) {
      setImageUploadMessage("");
      setImageUploadError("이미지 파일만 업로드할 수 있습니다.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setImageUploadMessage("");
      setImageUploadError("10MB 이하 이미지 파일만 업로드할 수 있습니다.");
      return;
    }

    setImageUploadError("");
    setImageUploadMessage("");
    setIsUploadingImage(true);
    try {
      const uploaded = await imageApiRepository.uploadImage({
        domain: imageUploadDomain,
        file,
        owner_type: ownerType,
        owner_id: normalizeOwnerId(),
      });
      run(() =>
        editor
          .chain()
          .focus()
          .setImage({ src: toRenderableImageUrl(uploaded.file_url), alt: uploaded.original_file_name, width: "50%" } as never)
          .createParagraphNear()
          .run(),
      );
      setImageUploadMessage(
        uploaded.relative_path
          ? `DrCT 저장소에 이미지를 업로드했습니다: ${uploaded.relative_path}`
          : "DrCT 저장소에 이미지를 업로드했습니다.",
      );
    } catch (error) {
      setImageUploadMessage("");
      setImageUploadError(error instanceof Error ? error.message : "이미지 업로드에 실패했습니다.");
    } finally {
      setIsUploadingImage(false);
    }
  };

  const handleUploadImageClick = () => {
    if (isUploadingImage) return;
    uploadInputRef.current?.click();
  };

  const handleUploadImageChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    void uploadEditorImage(file);
  };

  const insertTable = () => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run());
  const setFontSize = (fontSize: string) => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).setMark("textStyle", { fontSize }).run());
  const setTextColor = (color: string) => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).setMark("textStyle", { color }).run());
  const setBackgroundColor = (backgroundColor: string) =>
    run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).setMark("textStyle", { backgroundColor: backgroundColor === "transparent" ? null : backgroundColor }).run());
  const setTextAlign = (textAlign: "left" | "center" | "right") =>
    run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).updateAttributes("paragraph", { textAlign }).updateAttributes("heading", { textAlign }).run());
  const setImageWidth = (activeEditor: Editor | null, widthPercent: number) => {
    if (!activeEditor) return;
    run(() => activeEditor.chain().focus(undefined, { scrollIntoView: false }).updateAttributes("image", { width: `${widthPercent}%`, height: null }).run());
  };

  return (
    <div className="kms-editor-shell">
      <div className="kms-editor-toolbar" aria-label="Editor tools">
        <button type="button" title="Paragraph" className={buttonClass(editor?.isActive("paragraph"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).setParagraph().run())}>P</button>
        <button type="button" title="Heading 1" className={buttonClass(editor?.isActive("heading", { level: 1 }))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleHeading({ level: 1 }).run())}>H1</button>
        <button type="button" title="Heading 2" className={buttonClass(editor?.isActive("heading", { level: 2 }))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleHeading({ level: 2 }).run())}>H2</button>
        <button type="button" title="Heading 3" className={buttonClass(editor?.isActive("heading", { level: 3 }))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleHeading({ level: 3 }).run())}>H3</button>
        <select className="kms-editor-select" title="Font size" defaultValue="" onMouseDown={(event) => event.stopPropagation()} onChange={(event) => { if (event.target.value) setFontSize(event.target.value); event.target.value = ""; }}>
          <option value="">Size</option>
          {fontSizeOptions.map((size) => <option key={size} value={size}>{size}</option>)}
        </select>
        <select className="kms-editor-select" title="Text color" defaultValue="" onMouseDown={(event) => event.stopPropagation()} onChange={(event) => { if (event.target.value) setTextColor(event.target.value); event.target.value = ""; }}>
          <option value="">Text</option>
          {textColorOptions.map((color) => <option key={color} value={color}>{color}</option>)}
        </select>
        <select className="kms-editor-select" title="Background color" defaultValue="" onMouseDown={(event) => event.stopPropagation()} onChange={(event) => { if (event.target.value) setBackgroundColor(event.target.value); event.target.value = ""; }}>
          <option value="">Bg</option>
          {backgroundColorOptions.map((color) => <option key={color} value={color}>{color}</option>)}
        </select>
        <button type="button" title="Bold" className={buttonClass(editor?.isActive("bold"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleBold().run())}>B</button>
        <button type="button" title="Italic" className={buttonClass(editor?.isActive("italic"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleItalic().run())}>I</button>
        <button type="button" title="Underline" className={buttonClass(editor?.isActive("underline"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleUnderline().run())}>U</button>
        <button type="button" title="Align left" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => setTextAlign("left")}>Left</button>
        <button type="button" title="Align center" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => setTextAlign("center")}>Center</button>
        <button type="button" title="Align right" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => setTextAlign("right")}>Right</button>
        <button type="button" title="Bullet list" className={buttonClass(editor?.isActive("bulletList"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleBulletList().run())}>List</button>
        <button type="button" title="Ordered list" className={buttonClass(editor?.isActive("orderedList"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleOrderedList().run())}>1.</button>
        <button type="button" title="Quote" className={buttonClass(editor?.isActive("blockquote"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleBlockquote().run())}>Quote</button>
        <button type="button" title="Link" className={buttonClass(editor?.isActive("link"))} onMouseDown={keepSelection} onClick={setLink}>Link</button>
        <button type="button" title="Insert table" className="kms-editor-button" onMouseDown={keepSelection} onClick={insertTable}>Table</button>
        <button type="button" title="Add column" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).addColumnAfter().run())} disabled={!isTableSelected}>Col+</button>
        <button type="button" title="Add row" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).addRowAfter().run())} disabled={!isTableSelected}>Row+</button>
        <button type="button" title="Delete column" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).deleteColumn().run())} disabled={!isTableSelected}>Col-</button>
        <button type="button" title="Delete row" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).deleteRow().run())} disabled={!isTableSelected}>Row-</button>
        <button type="button" title="Delete table" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).deleteTable().run())} disabled={!isTableSelected}>Clear</button>
        <button type="button" title="Insert image URL" className="kms-editor-button" onMouseDown={keepSelection} onClick={insertImageUrl}>이미지 URL</button>
        {enableImageUpload ? (
          <>
            <button type="button" title="Upload image" className="kms-editor-button" onMouseDown={keepSelection} onClick={handleUploadImageClick} disabled={isUploadingImage}>
              {isUploadingImage ? "업로드 중" : "이미지 업로드"}
            </button>
            <input ref={uploadInputRef} className="kms-editor-file-input" type="file" accept="image/png,image/jpeg,image/jpg,image/gif,image/webp" onChange={handleUploadImageChange} />
          </>
        ) : null}
        <label className="kms-editor-image-size-control">
          <span>Image size</span>
          <input type="range" min="0" max="100" step="1" value={activeImageWidthValue} onMouseDown={(event) => event.stopPropagation()} onChange={(event) => setImageWidth(editor, Number(event.target.value))} disabled={!isImageSelected} />
          <output>{activeImageWidthValue}%</output>
        </label>
        <button type="button" title="Undo" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).undo().run())} disabled={!editor?.can().undo()}>Undo</button>
        <button type="button" title="Redo" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).redo().run())} disabled={!editor?.can().redo()}>Redo</button>
      </div>
      {imageUploadError ? <p className="kms-editor-error">{imageUploadError}</p> : null}
      {imageUploadMessage ? <p className="kms-editor-success">{imageUploadMessage}</p> : null}
      <EditorContent editor={editor} />
    </div>
  );
}

export default KmsRichEditor;
