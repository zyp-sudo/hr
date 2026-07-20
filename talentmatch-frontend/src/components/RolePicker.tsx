import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { Check, ChevronDown, Search, X } from "lucide-react";

// ─── useClickOutside ────────────────────────────────────────────

function useClickOutside<E extends HTMLElement = HTMLElement>(
  onOutside: () => void,
  enabled: boolean,
) {
  const ref = useRef<E | null>(null);
  const cbRef = useRef(onOutside);
  cbRef.current = onOutside;
  useEffect(() => {
    if (!enabled) return;
    const h = (e: MouseEvent | TouchEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) cbRef.current();
    };
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") cbRef.current();
    };
    document.addEventListener("mousedown", h);
    document.addEventListener("touchstart", h);
    document.addEventListener("keydown", k);
    return () => {
      document.removeEventListener("mousedown", h);
      document.removeEventListener("touchstart", h);
      document.removeEventListener("keydown", k);
    };
  }, [enabled]);
  return ref;
}

// ─── RolePicker ─────────────────────────────────────────────────

export interface RolePickerProps {
  roles: Array<{ id: string; name: string }>;
  selectedId: string;
  onSelect: (id: string) => void;
  label?: string;
  placeholder?: string;
}

export default function RolePicker({
  roles,
  selectedId,
  onSelect,
  label = "选择岗位",
  placeholder = "搜索岗位名称",
}: RolePickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [focusIdx, setFocusIdx] = useState(-1);
  const outerRef = useClickOutside<HTMLDivElement>(() => setOpen(false), open);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = useMemo(
    () => roles.find((r) => r.id === selectedId),
    [roles, selectedId],
  );

  const filtered = useMemo(() => {
    if (!query.trim()) return roles;
    const q = query.trim().toLowerCase();
    return roles.filter((r) => r.name.toLowerCase().includes(q));
  }, [roles, query]);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setFocusIdx(-1);
    triggerRef.current?.focus();
  }, []);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusIdx((i) => Math.min(i + 1, filtered.length - 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusIdx((i) => Math.max(i - 1, -1));
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const idx = focusIdx >= 0 ? focusIdx : 0;
      if (filtered[idx]) {
        onSelect(filtered[idx].id);
        close();
      } else {
        close();
      }
    }
  };

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  return (
    <div className="comp-evo-picker" ref={outerRef}>
      <label className="comp-evo-picker__label">{label}</label>
      <button
        ref={triggerRef}
        type="button"
        className={`comp-evo-picker__trigger${open ? " comp-evo-picker__trigger--open" : ""}`}
        onClick={(e) => {
          e.stopPropagation();
          open ? close() : setOpen(true);
        }}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <Search style={{ width: 14, flex: "none", opacity: 0.55 }} />
        <span className="comp-evo-picker__trigger-text">
          {selected?.name ?? "选择岗位…"}
        </span>
        <ChevronDown
          style={{
            width: 14,
            flex: "none",
            transition: "transform .2s",
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
          }}
        />
      </button>
      {open && (
        <div
          className="comp-evo-picker__menu"
          role="listbox"
          onKeyDown={onKeyDown}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="comp-evo-picker__search">
            <Search style={{ width: 13, flex: "none", opacity: 0.45 }} />
            <input
              ref={inputRef}
              className="comp-evo-picker__search-input"
              placeholder={placeholder}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setFocusIdx(-1);
              }}
              aria-label={placeholder}
            />
            {query && (
              <button
                type="button"
                className="comp-evo-picker__search-clear"
                onClick={() => setQuery("")}
                aria-label="清除搜索"
              >
                <X style={{ width: 12 }} />
              </button>
            )}
          </div>
          <div className="comp-evo-picker__list">
            {filtered.length === 0 ? (
              <div className="comp-evo-picker__empty">没有找到相关岗位</div>
            ) : (
              filtered.map((r, i) => {
                const sel = r.id === selectedId;
                return (
                  <div
                    key={r.id}
                    role="option"
                    aria-selected={sel}
                    className={`comp-evo-picker__option${sel ? " comp-evo-picker__option--selected" : ""}${i === focusIdx ? " comp-evo-picker__option--focused" : ""}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect(r.id);
                      close();
                    }}
                    onMouseEnter={() => setFocusIdx(i)}
                  >
                    <span className="comp-evo-picker__option-name">{r.name}</span>
                    {sel && <Check style={{ width: 14, flex: "none" }} />}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
