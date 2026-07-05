import { useCallback, useEffect, useRef, type ChangeEvent, type MouseEvent } from "react";
import type { Editor } from "@tiptap/core";
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
import StarterKit from "@tiptap/starter-kit";
import { sanitizeKmsHtml, toKmsEditableHtml } from "@/utils/kmsRichContent";

type KmsRichEditorProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  resetKey?: string | number;
};

const KmsImage = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      width: {
        default: null,
        parseHTML: (element) => element.getAttribute("width"),
        renderHTML: (attributes) => (attributes.width ? { width: attributes.width } : {}),
      },
      height: {
        default: null,
        parseHTML: (element) => element.getAttribute("height"),
        renderHTML: (attributes) => (attributes.height ? { height: attributes.height } : {}),
      },
    };
  },
});

const imageSizeOptions = [
  { label: "25%", value: "25%" },
  { label: "50%", value: "50%" },
  { label: "75%", value: "75%" },
  { label: "100%", value: "100%" },
];

function KmsRichEditor({ value, onChange, placeholder = "본문을 입력하세요.", resetKey = "kms-editor" }: KmsRichEditorProps) {
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const lastResetKeyRef = useRef<string | number>(resetKey);
  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextStyle,
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
      onChange(sanitizeKmsHtml(activeEditor.getHTML()));
    },
    editorProps: {
      attributes: {
        class: "kms-editor-content",
      },
    },
  });

  useEffect(() => {
    if (!editor) return;
    if (lastResetKeyRef.current === resetKey) return;
    if (editor.isFocused) return;
    const nextContent = toKmsEditableHtml(value);
    if (editor.getHTML() === nextContent) {
      lastResetKeyRef.current = resetKey;
      return;
    }
    editor.commands.setContent(nextContent, { emitUpdate: false });
    lastResetKeyRef.current = resetKey;
  }, [editor, resetKey, value]);

  const run = useCallback((action: () => void) => {
    if (!editor) return;
    action();
  }, [editor]);

  const keepSelection = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
  };

  const setLink = () => {
    if (!editor) return;
    const previousUrl = editor.getAttributes("link").href as string | undefined;
    const url = window.prompt("링크 URL을 입력하세요.", previousUrl || "https://");
    if (url === null) return;
    if (!url.trim()) {
      run(() => editor.chain().focus().extendMarkRange("link").unsetLink().run());
      return;
    }
    run(() => editor.chain().focus().extendMarkRange("link").setLink({ href: url.trim() }).run());
  };

  const openImagePicker = () => {
    imageInputRef.current?.click();
  };

  const insertImageFile = (file: File) => {
    if (!editor || !file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = () => {
      const src = String(reader.result || "");
      if (!src) return;
      run(() => editor.chain().focus().setImage({ src, alt: file.name, width: "100%" } as never).createParagraphNear().run());
    };
    reader.readAsDataURL(file);
  };

  const handleImageChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) insertImageFile(file);
    event.target.value = "";
  };

  const insertTable = () => run(() => editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run());

  const setImageWidth = (activeEditor: Editor | null, width: string) => {
    if (!activeEditor?.isActive("image")) return;
    run(() => activeEditor.chain().focus().updateAttributes("image", { width, height: null }).run());
  };

  const activeImageWidth = (editor?.getAttributes("image").width as string | null | undefined) || "100%";
  const isImageSelected = editor?.isActive("image") ?? false;
  const isTableSelected = editor?.isActive("table") ?? false;
  const buttonClass = (active = false) => (active ? "kms-editor-button active" : "kms-editor-button");

  return (
    <div className="kms-editor-shell">
      <div className="kms-editor-toolbar" aria-label="본문 편집 도구">
        <button type="button" title="문단" className={buttonClass(editor?.isActive("paragraph"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().setParagraph().run())}>문단</button>
        <button type="button" title="제목 1" className={buttonClass(editor?.isActive("heading", { level: 1 }))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().toggleHeading({ level: 1 }).run())}>제목1</button>
        <button type="button" title="제목 2" className={buttonClass(editor?.isActive("heading", { level: 2 }))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().toggleHeading({ level: 2 }).run())}>제목2</button>
        <button type="button" title="굵게" className={buttonClass(editor?.isActive("bold"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().toggleBold().run())}>B</button>
        <button type="button" title="기울임" className={buttonClass(editor?.isActive("italic"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().toggleItalic().run())}>I</button>
        <button type="button" title="밑줄" className={buttonClass(editor?.isActive("underline"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().toggleUnderline().run())}>U</button>
        <button type="button" title="글머리 목록" className={buttonClass(editor?.isActive("bulletList"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().toggleBulletList().run())}>목록</button>
        <button type="button" title="순서 있는 목록을 켜거나 끕니다." className={buttonClass(editor?.isActive("orderedList"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().toggleOrderedList().run())}>번호목록</button>
        <button type="button" title="인용" className={buttonClass(editor?.isActive("blockquote"))} onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().toggleBlockquote().run())}>인용</button>
        <button type="button" title="링크" className={buttonClass(editor?.isActive("link"))} onMouseDown={keepSelection} onClick={setLink}>링크</button>
        <button type="button" title="표 삽입" className="kms-editor-button" onMouseDown={keepSelection} onClick={insertTable}>표</button>
        <button type="button" title="열 추가" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().addColumnAfter().run())} disabled={!isTableSelected}>열+</button>
        <button type="button" title="행 추가" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().addRowAfter().run())} disabled={!isTableSelected}>행+</button>
        <button type="button" title="열 삭제" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().deleteColumn().run())} disabled={!isTableSelected}>열-</button>
        <button type="button" title="행 삭제" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().deleteRow().run())} disabled={!isTableSelected}>행-</button>
        <button type="button" title="표 삭제" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().deleteTable().run())} disabled={!isTableSelected}>표삭제</button>
        <button type="button" title="이미지 첨부" className="kms-editor-button" onMouseDown={keepSelection} onClick={openImagePicker}>이미지</button>
        <span className="kms-editor-toolbar-label">이미지 크기</span>
        {imageSizeOptions.map((option) => (
          <button
            key={option.value}
            type="button"
            title={`이미지 크기 ${option.label}`}
            className={buttonClass(isImageSelected && activeImageWidth === option.value)}
            onMouseDown={keepSelection}
            onClick={() => setImageWidth(editor, option.value)}
            disabled={!isImageSelected}
          >
            {option.label}
          </button>
        ))}
        <button type="button" title="실행취소" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().undo().run())} disabled={!editor?.can().undo()}>실행취소</button>
        <button type="button" title="다시실행" className="kms-editor-button" onMouseDown={keepSelection} onClick={() => run(() => editor?.chain().focus().redo().run())} disabled={!editor?.can().redo()}>다시실행</button>
        <input
          ref={imageInputRef}
          type="file"
          accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
          className="kms-editor-file-input"
          onChange={handleImageChange}
        />
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}

export default KmsRichEditor;
