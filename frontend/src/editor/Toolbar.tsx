import type { Editor } from "@tiptap/react";
import type { ReactNode } from "react";
import { Icon } from "../components/Icon";

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

interface ToolbarProps {
  editor: Editor;
  /** Disables the formatting tools (read-only roles, failed saves, previews). */
  disabled: boolean;
  /** Shown for anyone who may comment; not affected by `disabled` (commenters can't edit). */
  onComment?: () => void;
}

export function Toolbar({ editor, disabled, onComment }: ToolbarProps) {
  const chain = () => editor.chain().focus();
  const mod = navigator.platform.includes("Mac") ? "⌘" : "Ctrl+";

  function setStyle(style: Style) {
    if (style === "p") chain().setParagraph().run();
    else chain().setHeading({ level: Number(style) as 1 | 2 | 3 }).run();
  }

  return (
    <div className="toolbar" role="toolbar" aria-label="Formatting">
      <ToolButton label="Undo" shortcut={`${mod}Z`} disabled={disabled || !editor.can().undo()} onClick={() => chain().undo().run()}>
        <Icon name="undo" />
      </ToolButton>
      <ToolButton label="Redo" shortcut={`${mod}Y`} disabled={disabled || !editor.can().redo()} onClick={() => chain().redo().run()}>
        <Icon name="redo" />
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
        <Icon name="bullets" />
      </ToolButton>
      <ToolButton label="Numbered list" shortcut={`${mod}Shift+7`} active={editor.isActive("orderedList")} disabled={disabled} onClick={() => chain().toggleOrderedList().run()}>
        <Icon name="numbers" />
      </ToolButton>
      <ToolButton label="Quote" shortcut={`${mod}Shift+B`} active={editor.isActive("blockquote")} disabled={disabled} onClick={() => chain().toggleBlockquote().run()}>
        <Icon name="quote" />
      </ToolButton>
      {onComment && (
        <>
          <span className="tool-sep" />
          <ToolButton label="Comment" shortcut={`${mod}Alt+M`} onClick={onComment}>
            <Icon name="comment" />
          </ToolButton>
        </>
      )}
    </div>
  );
}
