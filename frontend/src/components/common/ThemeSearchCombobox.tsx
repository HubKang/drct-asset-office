import { KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, Search, X } from "lucide-react";
import type { MarketTheme } from "@/types/marketTheme";

export type ThemeComboboxValue = number | "ALL" | "UNASSIGNED" | null;

type Props = {
  themes: MarketTheme[];
  value: ThemeComboboxValue;
  onChange: (value: ThemeComboboxValue) => void;
  mode?: "picker" | "filter";
  disabled?: boolean;
  ariaLabel?: string;
};

type Option = { key: string; value: ThemeComboboxValue; title: string; meta: string };

export default function ThemeSearchCombobox({
  themes, value, onChange, mode = "picker", disabled = false, ariaLabel = "테마 선택",
}: Props) {
  const listboxId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [highlighted, setHighlighted] = useState(0);
  const [position, setPosition] = useState({ left: 0, top: 0, width: 360 });
  const selectedTheme = typeof value === "number" ? themes.find((theme) => theme.id === value) : null;
  const label = selectedTheme?.theme_name
    || (mode === "filter" ? (value === "UNASSIGNED" ? "미지정" : "테마 검색") : "테마 지정");

  const options = useMemo<Option[]>(() => {
    const needle = search.trim().toLocaleLowerCase("ko-KR");
    const special: Option[] = mode === "filter"
      ? [
          { key: "all", value: "ALL", title: "전체 테마", meta: "모든 브리핑" },
          { key: "unassigned", value: "UNASSIGNED", title: "미지정", meta: "테마가 지정되지 않은 브리핑" },
        ]
      : [{ key: "unassigned", value: null, title: "미지정", meta: "대표 테마 연결 해제" }];
    const themeOptions = themes
      .filter((theme) => theme.theme_level === "THEME" && theme.is_active === 1)
      .filter((theme) => !needle || theme.theme_name.toLocaleLowerCase("ko-KR").includes(needle)
        || (theme.parent_theme_name || "").toLocaleLowerCase("ko-KR").includes(needle))
      .map((theme) => ({
        key: String(theme.id), value: theme.id, title: theme.theme_name,
        meta: theme.parent_theme_name || "테마그룹 미지정",
      }));
    return needle ? themeOptions : [...special, ...themeOptions];
  }, [mode, search, themes]);

  const updatePosition = () => {
    const rect = rootRef.current?.getBoundingClientRect();
    if (!rect) return;
    const width = Math.min(380, Math.max(320, window.innerWidth - 24));
    const menuHeight = Math.min(menuRef.current?.getBoundingClientRect().height || 430, window.innerHeight - 24);
    setPosition({
      left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)),
      top: Math.max(12, Math.min(rect.bottom + 6, window.innerHeight - menuHeight - 12)),
      width,
    });
  };

  useEffect(() => {
    if (!open) return;
    updatePosition();
    setSearch(""); setHighlighted(0);
    requestAnimationFrame(() => searchRef.current?.focus());
    const close = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!rootRef.current?.contains(target) && !menuRef.current?.contains(target)) setOpen(false);
    };
    const reposition = () => updatePosition();
    document.addEventListener("mousedown", close);
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => {
      document.removeEventListener("mousedown", close);
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [open]);

  const select = (next: ThemeComboboxValue) => { onChange(next); setOpen(false); setSearch(""); };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const direction = event.key === "ArrowDown" ? 1 : -1;
      setHighlighted((current) => Math.max(0, Math.min(options.length - 1, current + direction)));
    } else if (event.key === "Enter" && options[highlighted]) {
      event.preventDefault(); select(options[highlighted].value);
    } else if (event.key === "Escape") {
      event.preventDefault(); setOpen(false);
    }
  };

  return <div className={`theme-search-select theme-search-select--${mode}`} ref={rootRef} onClick={(event) => event.stopPropagation()}>
    <button
      type="button" className="theme-search-select__trigger" disabled={disabled}
      role="combobox" aria-expanded={open} aria-controls={listboxId} aria-label={ariaLabel}
      title={selectedTheme ? `${selectedTheme.theme_name} · ${selectedTheme.parent_theme_name || "테마그룹 미지정"}` : label}
      onClick={() => setOpen((current) => !current)}
    >
      <span>{label}</span>
      {mode === "filter" && typeof value === "number" ? <X size={13} aria-label="필터 초기화" onClick={(event) => { event.stopPropagation(); select("ALL"); }} /> : <ChevronDown size={14} />}
    </button>
    {open ? createPortal(<div
      ref={menuRef} id={listboxId} className="theme-search-select__popover"
      role="listbox" style={{ left: position.left, top: position.top, width: position.width }}
      onClick={(event) => event.stopPropagation()}
    >
      <label className="theme-search-select__search"><Search size={15} /><input ref={searchRef} value={search} onChange={(event) => { setSearch(event.target.value); setHighlighted(0); }} onKeyDown={onKeyDown} placeholder="테마명 또는 테마그룹 검색" /></label>
      <div className="theme-search-select__options">
        {options.map((option, index) => <button key={option.key} type="button" role="option" aria-selected={option.value === value} className={`${index === highlighted ? "is-highlighted" : ""} ${option.value === value ? "is-selected" : ""}`} onMouseEnter={() => setHighlighted(index)} onClick={() => select(option.value)}><strong>{option.title}</strong><span>{option.meta}</span></button>)}
        {!options.length ? <p>검색된 테마가 없습니다.</p> : null}
      </div>
    </div>, document.body) : null}
  </div>;
}
