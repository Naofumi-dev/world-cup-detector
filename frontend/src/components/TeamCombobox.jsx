import { useEffect, useMemo, useRef, useState } from "react";

// Type-to-filter team picker with keyboard support. `teams` is an array of
// { name, elo, rank } already ordered (ranked teams first). Replaces the
// unwieldy 336-option native <select>.
export default function TeamCombobox({ teams, value, onChange, accent = "neutral" }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [hi, setHi] = useState(0);
  const ref = useRef(null);
  const listRef = useRef(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const base = q ? teams.filter((t) => t.name.toLowerCase().includes(q)) : teams;
    return base.slice(0, 80);
  }, [teams, query]);

  useEffect(() => {
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => setHi(0), [query, open]);

  useEffect(() => {
    if (open && listRef.current?.children[hi]) {
      listRef.current.children[hi].scrollIntoView({ block: "nearest" });
    }
  }, [hi, open]);

  const choose = (name) => {
    onChange(name);
    setOpen(false);
    setQuery("");
  };

  const onKey = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setHi((h) => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHi((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (open && filtered[hi]) choose(filtered[hi].name);
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
      ref.current?.querySelector("input")?.blur();
    }
  };

  return (
    <div className={`combo ${accent} ${open ? "open" : ""}`} ref={ref}>
      <input
        className="combo-input"
        value={(open ? query : value) ?? ""}
        placeholder={open ? value || "Search team…" : ""}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        spellCheck="false"
      />
      <span className="combo-caret" aria-hidden="true" onClick={() => setOpen((o) => !o)}>
        ▾
      </span>
      {open && (
        <ul className="combo-list" ref={listRef} role="listbox">
          {filtered.length === 0 && <li className="combo-empty">No teams found</li>}
          {filtered.map((t, i) => (
            <li
              key={t.name}
              role="option"
              aria-selected={t.name === value}
              className={`combo-opt ${i === hi ? "hi" : ""} ${t.name === value ? "sel" : ""}`}
              onMouseEnter={() => setHi(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(t.name);
              }}
            >
              <span className={`combo-rank ${t.rank ? "" : "dim"}`}>{t.rank ? `#${t.rank}` : "·"}</span>
              <span className="combo-name">{t.name}</span>
              <span className="combo-elo">{Math.round(t.elo)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
