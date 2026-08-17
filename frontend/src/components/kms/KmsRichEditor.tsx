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
import { NodeSelection, TextSelection } from "@tiptap/pm/state";
import StarterKit from "@tiptap/starter-kit";
import { createPortal } from "react-dom";
import { AlignCenter, AlignLeft, AlignRight, ImagePlus, Link2, List, ListOrdered, Quote, Redo2, Table2, Trash2, Undo2, Upload, X } from "lucide-react";
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
  onSessionUploadedImageUrlsChange?: (urls: string[]) => void;
  onRemovedImageUrlsChange?: (urls: string[]) => void;
};

const KmsImage = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      width: {
        default: null,
        parseHTML: (element) => element.getAttribute("data-kms-width") || element.getAttribute("width") || element.style.width || null,
        renderHTML: (attributes) => {
          if (!attributes.width) return {};
          const numericWidth = Math.max(20, Math.min(100, Number.parseInt(String(attributes.width), 10) || 100));
          return {
            width: `${numericWidth}%`,
            "data-kms-width": String(numericWidth),
            style: `width: ${numericWidth}%; max-width: 100%; height: auto;`,
          };
        },
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
const textColorOptions = [
  { value: "#0f172a", label: "기본(검정)" },
  { value: "#2563eb", label: "파랑" },
  { value: "#16a34a", label: "초록" },
  { value: "#dc2626", label: "빨강" },
  { value: "#9333ea", label: "보라" },
  { value: "#ea580c", label: "주황" },
];
const backgroundColorOptions = [
  { value: "transparent", label: "없음" },
  { value: "#fef3c7", label: "연노랑" },
  { value: "#dcfce7", label: "연두" },
  { value: "#dbeafe", label: "하늘" },
  { value: "#fce7f3", label: "연분홍" },
  { value: "#fee2e2", label: "연빨강" },
];

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
  onSessionUploadedImageUrlsChange,
  onRemovedImageUrlsChange,
}: KmsRichEditorProps) {
  const lastAppliedResetKeyRef = useRef<string | number>(resetKey);
  const lastEmittedHtmlRef = useRef("");
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const shellRef = useRef<HTMLDivElement | null>(null);
  const imageActionModalRef = useRef<HTMLElement | null>(null);
  const uploadedImageUrlsRef = useRef<string[]>([]);
  const removedImageUrlsRef = useRef<string[]>([]);
  const uploadChangeCallbackRef = useRef(onSessionUploadedImageUrlsChange);
  const removedChangeCallbackRef = useRef(onRemovedImageUrlsChange);
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const [imageUploadError, setImageUploadError] = useState("");
  const [imageUploadMessage, setImageUploadMessage] = useState("");
  const [selectionState, setSelectionState] = useState({ isImage: false, isTable: false, imageWidth: 100 });
  const [isImageActionModalOpen, setIsImageActionModalOpen] = useState(false);

  uploadChangeCallbackRef.current = onSessionUploadedImageUrlsChange;
  removedChangeCallbackRef.current = onRemovedImageUrlsChange;

  const syncSelectionState = useCallback((activeEditor: Editor) => {
    const isImage = activeEditor.isActive("image");
    const rawWidth = isImage ? activeEditor.getAttributes("image").width : null;
    setSelectionState({
      isImage,
      isTable: activeEditor.isActive("table"),
      imageWidth: isImage ? Math.max(20, Math.min(100, Number.parseInt(String(rawWidth || "100"), 10) || 100)) : 100,
    });
  }, []);

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
      syncSelectionState(activeEditor);
    },
    onSelectionUpdate: ({ editor: activeEditor }) => syncSelectionState(activeEditor),
    editorProps: {
      attributes: {
        class: "kms-editor-content",
        "data-testid": "kms-rich-editor-content",
      },
      handleClick: (view, position, event) => {
        if (event.button !== 0 || event.detail !== 1 || event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) return false;
        const target = event.target instanceof HTMLElement ? event.target : null;
        if (target?.closest("img")) {
          setIsImageActionModalOpen(true);
          return false;
        }
        if (target?.closest("a, table")) return false;
        const selection = TextSelection.near(view.state.doc.resolve(position));
        view.dispatch(view.state.tr.setSelection(selection));
        return true;
      },
      handleKeyDown: (view, event) => {
        if ((event.key !== "Delete" && event.key !== "Backspace") || !(view.state.selection instanceof NodeSelection) || view.state.selection.node.type.name !== "image") {
          return false;
        }
        event.preventDefault();
        const source = String(view.state.selection.node.attrs.src || "").trim();
        if (source && !removedImageUrlsRef.current.includes(source)) {
          removedImageUrlsRef.current = [...removedImageUrlsRef.current, source];
          removedChangeCallbackRef.current?.(removedImageUrlsRef.current);
        }
        view.dispatch(view.state.tr.deleteSelection().scrollIntoView());
        setIsImageActionModalOpen(false);
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

  useEffect(() => {
    uploadedImageUrlsRef.current = [];
    removedImageUrlsRef.current = [];
    uploadChangeCallbackRef.current?.([]);
    removedChangeCallbackRef.current?.([]);
  }, [resetKey]);

  useEffect(() => {
    if (!editor) return;
    const clearImageSelection = (event: PointerEvent) => {
      if (shellRef.current?.contains(event.target as Node)) return;
      if (imageActionModalRef.current?.contains(event.target as Node)) return;
      const { selection } = editor.state;
      if (!(selection instanceof NodeSelection) || selection.node.type.name !== "image") return;
      editor.view.dispatch(editor.state.tr.setSelection(TextSelection.near(editor.state.doc.resolve(selection.from))));
    };
    document.addEventListener("pointerdown", clearImageSelection, true);
    return () => document.removeEventListener("pointerdown", clearImageSelection, true);
  }, [editor]);

  useEffect(() => {
    if (selectionState.isImage) setIsImageActionModalOpen(true);
    else setIsImageActionModalOpen(false);
  }, [selectionState.isImage]);

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
  const isImageSelected = selectionState.isImage;
  const isTableSelected = selectionState.isTable;
  const activeImageWidthValue = selectionState.imageWidth;

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
      const renderableUrl = toRenderableImageUrl(uploaded.file_url);
      run(() =>
        editor
          .chain()
          .focus()
          .setImage({ src: renderableUrl, alt: uploaded.original_file_name, width: "50%" } as never)
          .createParagraphNear()
          .run(),
      );
      if (!uploadedImageUrlsRef.current.includes(renderableUrl)) {
        uploadedImageUrlsRef.current = [...uploadedImageUrlsRef.current, renderableUrl];
        uploadChangeCallbackRef.current?.(uploadedImageUrlsRef.current);
      }
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
    const normalizedWidth = Math.max(20, Math.min(100, widthPercent));
    run(() => activeEditor.chain().focus(undefined, { scrollIntoView: false }).updateAttributes("image", { width: `${normalizedWidth}%` }).run());
    setSelectionState((current) => ({ ...current, imageWidth: normalizedWidth }));
  };

  const deleteSelectedImage = () => {
    if (!editor || !(editor.state.selection instanceof NodeSelection) || editor.state.selection.node.type.name !== "image") return;
    const source = String(editor.state.selection.node.attrs.src || "").trim();
    if (source && !removedImageUrlsRef.current.includes(source)) {
      removedImageUrlsRef.current = [...removedImageUrlsRef.current, source];
      removedChangeCallbackRef.current?.(removedImageUrlsRef.current);
    }
    editor.view.dispatch(editor.state.tr.deleteSelection().scrollIntoView());
    setIsImageActionModalOpen(false);
  };

  return (
    <div ref={shellRef} className="kms-editor-shell">
      <div className="kms-editor-toolbar" aria-label="본문 편집 도구">
        <div className="kms-editor-toolbar-row kms-editor-toolbar-primary">
          <div className="kms-editor-tool-group" aria-label="문단 형식">
            <button type="button" title="본문" className={buttonClass(editor?.isActive("paragraph"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).setParagraph().run())}>본문</button>
            <button type="button" title="제목 1" className={buttonClass(editor?.isActive("heading", { level: 1 }))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleHeading({ level: 1 }).run())}>H1</button>
            <button type="button" title="제목 2" className={buttonClass(editor?.isActive("heading", { level: 2 }))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleHeading({ level: 2 }).run())}>H2</button>
            <button type="button" title="제목 3" className={buttonClass(editor?.isActive("heading", { level: 3 }))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleHeading({ level: 3 }).run())}>H3</button>
          </div>
          <div className="kms-editor-tool-group" aria-label="글자 스타일">
            <select className="kms-editor-select" title="글자 크기" aria-label="글자 크기" defaultValue="" onMouseDown={(event) => event.stopPropagation()} onChange={(event) => { if (event.target.value) setFontSize(event.target.value); event.target.value = ""; }}><option value="">크기</option>{fontSizeOptions.map((size) => <option key={size} value={size}>{size}</option>)}</select>
            <select className="kms-editor-select" title="글자 색" aria-label="글자 색" defaultValue="" onMouseDown={(event) => event.stopPropagation()} onChange={(event) => { if (event.target.value) setTextColor(event.target.value); event.target.value = ""; }}><option value="">글자색</option>{textColorOptions.map((color) => <option key={color.value} value={color.value}>{color.label}</option>)}</select>
            <select className="kms-editor-select" title="배경 색" aria-label="배경 색" defaultValue="" onMouseDown={(event) => event.stopPropagation()} onChange={(event) => { if (event.target.value) setBackgroundColor(event.target.value); event.target.value = ""; }}><option value="">배경색</option>{backgroundColorOptions.map((color) => <option key={color.value} value={color.value}>{color.label}</option>)}</select>
            <button type="button" title="굵게" className={buttonClass(editor?.isActive("bold"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleBold().run())}><strong>B</strong></button>
            <button type="button" title="기울임" className={buttonClass(editor?.isActive("italic"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleItalic().run())}><em>I</em></button>
            <button type="button" title="밑줄" className={buttonClass(editor?.isActive("underline"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleUnderline().run())}><u>U</u></button>
          </div>
          <div className="kms-editor-tool-group" aria-label="정렬">
            <button type="button" title="왼쪽 정렬" className="kms-editor-button icon-only" onMouseDown={keepSelection} onClick={() => setTextAlign("left")}><AlignLeft size={15} /></button>
            <button type="button" title="가운데 정렬" className="kms-editor-button icon-only" onMouseDown={keepSelection} onClick={() => setTextAlign("center")}><AlignCenter size={15} /></button>
            <button type="button" title="오른쪽 정렬" className="kms-editor-button icon-only" onMouseDown={keepSelection} onClick={() => setTextAlign("right")}><AlignRight size={15} /></button>
          </div>
          <div className="kms-editor-tool-group" aria-label="목록과 인용">
            <button type="button" title="글머리 목록" className={buttonClass(editor?.isActive("bulletList"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleBulletList().run())}><List size={15} /></button>
            <button type="button" title="번호 목록" className={buttonClass(editor?.isActive("orderedList"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleOrderedList().run())}><ListOrdered size={15} /></button>
            <button type="button" title="인용" className={buttonClass(editor?.isActive("blockquote"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).toggleBlockquote().run())}><Quote size={15} /></button>
            <button type="button" title="링크" className={buttonClass(editor?.isActive("link"))} onMouseDown={keepSelection} onClick={setLink}><Link2 size={15} /></button>
          </div>
          <div className="kms-editor-tool-group" aria-label="편집 기록">
            <button type="button" title="실행 취소" className="kms-editor-button icon-only" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).undo().run())} disabled={!editor?.can().undo()}><Undo2 size={15} /></button>
            <button type="button" title="다시 실행" className="kms-editor-button icon-only" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).redo().run())} disabled={!editor?.can().redo()}><Redo2 size={15} /></button>
          </div>
        </div>
        <div className="kms-editor-toolbar-row kms-editor-toolbar-context">
          <div className="kms-editor-tool-group" aria-label="삽입">
            <button type="button" title="표 삽입" className="kms-editor-button" onMouseDown={keepSelection} onClick={insertTable}><Table2 size={15} />표</button>
            <button type="button" title="이미지 URL 삽입" className="kms-editor-button" onMouseDown={keepSelection} onClick={insertImageUrl}><ImagePlus size={15} />이미지 URL</button>
            {enableImageUpload ? <><button type="button" title="이미지 업로드" className="kms-editor-button" onMouseDown={keepSelection} onClick={handleUploadImageClick} disabled={isUploadingImage}><Upload size={15} />{isUploadingImage ? "업로드 중" : "이미지 업로드"}</button><input ref={uploadInputRef} className="kms-editor-file-input" type="file" accept="image/png,image/jpeg,image/jpg,image/gif,image/webp" onChange={handleUploadImageChange} /></> : null}
          </div>
          {isTableSelected ? <div className="kms-editor-tool-group kms-editor-context-group" aria-label="표 편집"><span className="kms-editor-context-label">표 편집</span><button type="button" title="열 추가" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).addColumnAfter().run())}>열 추가</button><button type="button" title="행 추가" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).addRowAfter().run())}>행 추가</button><button type="button" title="열 삭제" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).deleteColumn().run())}>열 삭제</button><button type="button" title="행 삭제" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).deleteRow().run())}>행 삭제</button><button type="button" title="표 지우기" className="kms-editor-button danger" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus(undefined, { scrollIntoView: false }).deleteTable().run())}>표 지우기</button></div> : null}
          {!isTableSelected ? <span className="kms-editor-context-placeholder">이미지를 선택하면 이미지 작업 모달이 열립니다.</span> : null}
        </div>
      </div>
      {imageUploadError ? <p className="kms-editor-error">{imageUploadError}</p> : null}
      {imageUploadMessage ? <p className="kms-editor-success">{imageUploadMessage}</p> : null}
      <EditorContent editor={editor} />
      {isImageSelected && isImageActionModalOpen ? createPortal(
        <div className="kms-image-action-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setIsImageActionModalOpen(false); }}>
          <section ref={imageActionModalRef} className="kms-image-action-modal" role="dialog" aria-modal="true" aria-labelledby="kms-image-action-title" onMouseDown={(event) => event.stopPropagation()}>
            <header className="kms-image-action-modal-header">
              <div>
                <strong id="kms-image-action-title">이미지 작업</strong>
                <p>선택한 이미지의 크기를 조절하거나 삭제합니다.</p>
              </div>
              <button type="button" className="kms-image-action-close" aria-label="이미지 작업 닫기" onMouseDown={keepSelection} onClick={() => setIsImageActionModalOpen(false)}><X size={18} /></button>
            </header>
            <div className="kms-image-action-modal-body">
              <label className="kms-image-action-size">
                <span>이미지 크기 <strong>{activeImageWidthValue}%</strong></span>
                <input type="range" min="20" max="100" step="5" value={activeImageWidthValue} onMouseDown={(event) => event.stopPropagation()} onChange={(event) => setImageWidth(editor, Number(event.target.value))} />
              </label>
              <div className="kms-image-size-presets" aria-label="이미지 크기 빠른 선택">
                {[25, 50, 75, 100].map((size) => <button key={size} type="button" className={activeImageWidthValue === size ? "active" : ""} onMouseDown={keepSelection} onClick={() => setImageWidth(editor, size)}>{size}%</button>)}
              </div>
              <p className="kms-image-action-help">Delete 후 수정 내용을 저장하면 연결된 물리 이미지도 함께 삭제됩니다.</p>
            </div>
            <footer className="kms-image-action-modal-footer">
              <button type="button" className="kms-image-action-delete" onMouseDown={keepSelection} onClick={deleteSelectedImage}><Trash2 size={16} />Delete</button>
              <button type="button" className="kms-image-action-done" onMouseDown={keepSelection} onClick={() => setIsImageActionModalOpen(false)}>완료</button>
            </footer>
          </section>
        </div>,
        document.body,
      ) : null}
    </div>
  );
}

export default KmsRichEditor;
