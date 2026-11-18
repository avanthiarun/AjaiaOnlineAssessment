import type { Editor } from "@tiptap/react";
import type { ReactNode } from "react";

const ICONS = {
  undo: "M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z",
  redo: "M18.4 10.6C16.55 8.99 14.15 8 11.5 8c-4.65 0-8.58 3.03-9.96 7.22L3.9 16c1.05-3.19 4.05-5.5 7.6-5.5 1.95 0 3.73.72 5.12 1.88L13 16h9V7l-3.6 3.6z",
  bullets:
    "M4 10.5c-.83 0-1.5.67-1.5 1.5s.67 1.5 1.5 1.5 1.5-.67 1.5-1.5-.67-1.5-1.5-1.5zm0-6c-.83 0-1.5.67-1.5 1.5S3.17 7.5 4 7.5 5.5 6.83 5.5 6 4.83 4.5 4 4.5zm0 12c-.83 0-1.5.68-1.5 1.5s.68 1.5 1.5 1.5 1.5-.68 1.5-1.5-.67-1.5-1.5-1.5zM7 19h14v-2H7v2zm0-6h14v-2H7v2zm0-8v2h14V5H7z",
  numbers:
    "M2 17h2v.5H3v1h1v.5H2v1h3v-4H2v1zm1-9h1V4H2v1h1v3zm-1 3h1.8L2 13.1v.9h3v-1H3.2L5 10.9V10H2v1zm5-6v2h14V5H7zm0 14h14v-2H7v2zm0-6h14v-2H7v2z",
  quote: "M6 17h3l2-4V7H5v6h3zm8 0h3l2-4V7h-6v6h3z",
};

function Icon({ path }: { path: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path d={path} fill="currentColor" />
    </svg>
  );
}

interface ButtonProps {
  label: string;
  shortcut?: string;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}

function ToolButton({ label, shortcut, active = false, disabled = false, onClick, children }: ButtonProps) {
  return (
    <button
      type="button"
      className={`tool-btn${active ? " is-active" : ""}`}
      aria-label={label}
      aria-pressed={active}
      title={shortcut ? `${label} (${shortcut})` : label}
      disabled={disabled}
      onMouseDown={(e) => e.preventDefault()} // keep the editor's selection
      onClick={onClick}
    >
      {children}
    </button>
  );
}

type Style = "p" | "1" | "2" | "3";

function currentStyle(editor: Editor): Style {
  for (const level of [1, 2, 3] as const) {
    if (editor.isActive("heading", { level })) return String(level) as Style;
  }
  return "p";
}

export function Toolbar({ editor, disabled }: { editor: Editor; disabled: boolean }) {
  const chain = () => editor.chain().focus();
  const mod = navigator.platform.includes("Mac") ? "⌘" : "Ctrl+";

  function setStyle(style: Style) {
    if (style === "p") chain().setParagraph().run();
    else chain().setHeading({ level: Number(style) as 1 | 2 | 3 }).run();
  }

  return (
    <div className="toolbar" role="toolbar" aria-label="Formatting">
      <ToolButton label="Undo" shortcut={`${mod}Z`} disabled={disabled || !editor.can().undo()} onClick={() => chain().undo().run()}>
        <Icon path={ICONS.undo} />
      </ToolButton>
      <ToolButton label="Redo" shortcut={`${mod}Y`} disabled={disabled || !editor.can().redo()} onClick={() => chain().redo().run()}>
        <Icon path={ICONS.redo} />
      </ToolButton>
      <span className="tool-sep" />
      <select
        className="style-select"
        aria-label="Text style"
        value={currentStyle(editor)}
        disabled={disabled}
        onChange={(e) => setStyle(e.target.value as Style)}
      >
        <option value="p">Normal text</option>
        <option value="1">Heading 1</option>
        <option value="2">Heading 2</option>
        <option value="3">Heading 3</option>
      </select>
      <span className="tool-sep" />
      <ToolButton label="Bold" shortcut={`${mod}B`} active={editor.isActive("bold")} disabled={disabled} onClick={() => chain().toggleBold().run()}>
        <b>B</b>
      </ToolButton>
      <ToolButton label="Italic" shortcut={`${mod}I`} active={editor.isActive("italic")} disabled={disabled} onClick={() => chain().toggleItalic().run()}>
        <i style={{ fontFamily: "Georgia, serif" }}>I</i>
      </ToolButton>
      <ToolButton label="Underline" shortcut={`${mod}U`} active={editor.isActive("underline")} disabled={disabled} onClick={() => chain().toggleUnderline().run()}>
        <u>U</u>
      </ToolButton>
      <ToolButton label="Strikethrough" shortcut={`${mod}Shift+S`} active={editor.isActive("strike")} disabled={disabled} onClick={() => chain().toggleStrike().run()}>
        <s>S</s>
      </ToolButton>
      <span className="tool-sep" />
      <ToolButton label="Bulleted list" shortcut={`${mod}Shift+8`} active={editor.isActive("bulletList")} disabled={disabled} onClick={() => chain().toggleBulletList().run()}>
        <Icon path={ICONS.bullets} />
      </ToolButton>
      <ToolButton label="Numbered list" shortcut={`${mod}Shift+7`} active={editor.isActive("orderedList")} disabled={disabled} onClick={() => chain().toggleOrderedList().run()}>
        <Icon path={ICONS.numbers} />
      </ToolButton>
      <ToolButton label="Quote" shortcut={`${mod}Shift+B`} active={editor.isActive("blockquote")} disabled={disabled} onClick={() => chain().toggleBlockquote().run()}>
        <Icon path={ICONS.quote} />
      </ToolButton>
    </div>
  );
}
