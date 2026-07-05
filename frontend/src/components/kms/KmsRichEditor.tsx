import { useCallback, useEffect, useRef, type ChangeEvent } from "react";
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
};

function KmsRichEditor({ value, onChange, placeholder = "본문을 입력하세요." }: KmsRichEditorProps) {
  const imageInputRef = useRef<HTMLInputElement | null>(null);
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
      Image.configure({
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
    const nextContent = toKmsEditableHtml(value);
    if (editor.getHTML() === nextContent) return;
    editor.commands.setContent(nextContent, { emitUpdate: false });
  }, [editor, value]);

  const run = useCallback((action: () => void) => {
    if (!editor) return;
    action();
    editor.commands.focus();
  }, [editor]);

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
      run(() => editor.chain().focus().setImage({ src, alt: file.name }).run());
    };
    reader.readAsDataURL(file);
  };

  const handleImageChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) insertImageFile(file);
    event.target.value = "";
  };

  const insertTable = () => run(() => editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run());

  const buttonClass = (active = false) => (active ? "kms-editor-button active" : "kms-editor-button");

  return (
    <div className="kms-editor-shell">
      <div className="kms-editor-toolbar" aria-label="본문 편집 도구">
        <button type="button" className={buttonClass(editor?.isActive("paragraph"))} onClick={() => run(() => editor?.chain().focus().setParagraph().run())}>문단</button>
        <button type="button" className={buttonClass(editor?.isActive("heading", { level: 1 }))} onClick={() => run(() => editor?.chain().focus().toggleHeading({ level: 1 }).run())}>제목1</button>
        <button type="button" className={buttonClass(editor?.isActive("heading", { level: 2 }))} onClick={() => run(() => editor?.chain().focus().toggleHeading({ level: 2 }).run())}>제목2</button>
        <button type="button" className={buttonClass(editor?.isActive("bold"))} onClick={() => run(() => editor?.chain().focus().toggleBold().run())}>B</button>
        <button type="button" className={buttonClass(editor?.isActive("italic"))} onClick={() => run(() => editor?.chain().focus().toggleItalic().run())}>I</button>
        <button type="button" className={buttonClass(editor?.isActive("underline"))} onClick={() => run(() => editor?.chain().focus().toggleUnderline().run())}>U</button>
        <button type="button" className={buttonClass(editor?.isActive("bulletList"))} onClick={() => run(() => editor?.chain().focus().toggleBulletList().run())}>목록</button>
        <button type="button" className={buttonClass(editor?.isActive("orderedList"))} onClick={() => run(() => editor?.chain().focus().toggleOrderedList().run())}>번호</button>
        <button type="button" className={buttonClass(editor?.isActive("blockquote"))} onClick={() => run(() => editor?.chain().focus().toggleBlockquote().run())}>인용</button>
        <button type="button" className={buttonClass(editor?.isActive("link"))} onClick={setLink}>링크</button>
        <button type="button" className="kms-editor-button" onClick={insertTable}>표</button>
        <button type="button" className="kms-editor-button" onClick={() => run(() => editor?.chain().focus().addColumnAfter().run())}>열+</button>
        <button type="button" className="kms-editor-button" onClick={() => run(() => editor?.chain().focus().addRowAfter().run())}>행+</button>
        <button type="button" className="kms-editor-button" onClick={openImagePicker}>이미지</button>
        <button type="button" className="kms-editor-button" onClick={() => run(() => editor?.chain().focus().undo().run())}>실행취소</button>
        <button type="button" className="kms-editor-button" onClick={() => run(() => editor?.chain().focus().redo().run())}>다시실행</button>
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
