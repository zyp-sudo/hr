import { useMemo, useState } from "react";
import type { Interview, InterviewTag, CalendarSubView } from "../../types/interview";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";

interface Props {
  interviews: Interview[];
  tags: InterviewTag[];
  onSelect: (interview: Interview) => void;
  onCreate: (date: Date) => void;
}

const statusColors: Record<string, string> = {
  pending: "#facc15",
  scheduled: "#60a5fa",
  in_progress: "#4ade80",
  completed: "#9bf2e9",
  cancelled: "#f87171",
};

type DateCell = {
  date: Date;
  isCurrentMonth: boolean;
  isToday: boolean;
  dayInterviews: Interview[];
};

export default function InterviewCalendar({ interviews, tags, onSelect, onCreate }: Props) {
  const [view, setView] = useState<CalendarSubView>("month");
  const [cursor, setCursor] = useState(new Date());

  const goPrev = () => {
    const d = new Date(cursor);
    if (view === "month") d.setMonth(d.getMonth() - 1);
    else if (view === "week") d.setDate(d.getDate() - 7);
    else d.setDate(d.getDate() - 1);
    setCursor(d);
  };

  const goNext = () => {
    const d = new Date(cursor);
    if (view === "month") d.setMonth(d.getMonth() + 1);
    else if (view === "week") d.setDate(d.getDate() + 7);
    else d.setDate(d.getDate() + 1);
    setCursor(d);
  };

  const goToday = () => setCursor(new Date());

  const title = useMemo(() => {
    if (view === "month") return `${cursor.getFullYear()}年 ${cursor.getMonth() + 1}月`;
    if (view === "week") {
      const start = new Date(cursor);
      start.setDate(start.getDate() - start.getDay());
      const end = new Date(start);
      end.setDate(end.getDate() + 6);
      return `${start.getMonth() + 1}/${start.getDate()} — ${end.getMonth() + 1}/${end.getDate()}`;
    }
    return `${cursor.getFullYear()}年 ${cursor.getMonth() + 1}月 ${cursor.getDate()}日`;
  }, [cursor, view]);

  // Group interviews by date
  const interviewByDate = useMemo(() => {
    const map = new Map<string, Interview[]>();
    interviews.forEach((iv) => {
      try {
        const d = new Date(iv.startsAt);
        const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        const arr = map.get(key) || [];
        arr.push(iv);
        map.set(key, arr);
      } catch { /* ignore bad dates */ }
    });
    return map;
  }, [interviews]);

  // Build month grid
  const monthCells = useMemo((): DateCell[] => {
    const year = cursor.getFullYear();
    const month = cursor.getMonth();
    const firstDay = new Date(year, month, 1);
    const startDay = firstDay.getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const today = new Date();
    const cells: DateCell[] = [];

    // Previous month days
    const prevMonthDays = new Date(year, month, 0).getDate();
    for (let i = startDay - 1; i >= 0; i--) {
      const d = new Date(year, month - 1, prevMonthDays - i);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      cells.push({ date: d, isCurrentMonth: false, isToday: false, dayInterviews: interviewByDate.get(key) || [] });
    }

    // Current month days
    for (let i = 1; i <= daysInMonth; i++) {
      const d = new Date(year, month, i);
      const key = `${year}-${String(month + 1).padStart(2, "0")}-${String(i).padStart(2, "0")}`;
      cells.push({
        date: d,
        isCurrentMonth: true,
        isToday: d.toDateString() === today.toDateString(),
        dayInterviews: interviewByDate.get(key) || [],
      });
    }

    // Fill remaining cells
    const remaining = 42 - cells.length;
    for (let i = 1; i <= remaining; i++) {
      const d = new Date(year, month + 1, i);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      cells.push({ date: d, isCurrentMonth: false, isToday: false, dayInterviews: interviewByDate.get(key) || [] });
    }

    return cells;
  }, [cursor, interviewByDate]);

  // Week view — 7 days starting from Sunday
  const weekDays = useMemo(() => {
    const start = new Date(cursor);
    start.setDate(start.getDate() - start.getDay());
    const days: DateCell[] = [];
    const today = new Date();
    for (let i = 0; i < 7; i++) {
      const d = new Date(start);
      d.setDate(d.getDate() + i);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      days.push({
        date: d,
        isCurrentMonth: true,
        isToday: d.toDateString() === today.toDateString(),
        dayInterviews: interviewByDate.get(key) || [],
      });
    }
    return days;
  }, [cursor, interviewByDate]);

  // Day view
  const dayHours = useMemo(() => {
    const key = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}-${String(cursor.getDate()).padStart(2, "0")}`;
    const dayInterviews = interviewByDate.get(key) || [];
    const hours: { hour: number; interviews: Interview[] }[] = [];
    for (let h = 0; h < 24; h++) {
      hours.push({
        hour: h,
        interviews: dayInterviews.filter((iv) => {
          try {
            return new Date(iv.startsAt).getHours() === h;
          } catch { return false; }
        }),
      });
    }
    return hours;
  }, [cursor, interviewByDate]);

  const dayNames = ["日", "一", "二", "三", "四", "五", "六"];

  return (
    <div className="iv-calendar">
      {/* Header */}
      <div className="iv-calendar__head">
        <div className="iv-calendar__nav">
          <button onClick={goPrev}><ChevronLeft /></button>
          <h3 onClick={goToday}>{title}</h3>
          <button onClick={goNext}><ChevronRight /></button>
        </div>
        <div className="iv-calendar__views">
          {(["month", "week", "day"] as CalendarSubView[]).map((v) => (
            <button key={v} className={view === v ? "active" : ""} onClick={() => setView(v)}>
              {v === "month" ? "月" : v === "week" ? "周" : "日"}
            </button>
          ))}
        </div>
      </div>

      {/* Month view */}
      {view === "month" && (
        <div className="iv-calendar__month">
          <div className="iv-calendar__day-headers">
            {dayNames.map((d) => <span key={d}>{d}</span>)}
          </div>
          <div className="iv-calendar__grid">
            {monthCells.map((cell, idx) => (
              <div
                key={idx}
                className={`iv-calendar__cell ${cell.isCurrentMonth ? "" : "iv-calendar__cell--muted"} ${cell.isToday ? "iv-calendar__cell--today" : ""}`}
                onClick={() => { if (cell.isCurrentMonth) onCreate(cell.date); }}
              >
                <span className="iv-calendar__cell-date">{cell.date.getDate()}</span>
                {cell.isCurrentMonth && (
                  <div className="iv-calendar__cell-events">
                    {cell.dayInterviews.slice(0, 3).map((iv) => (
                      <button
                        key={iv.id}
                        className="iv-calendar__event"
                        style={{ borderLeftColor: statusColors[iv.status] || "#666" }}
                        onClick={(e) => { e.stopPropagation(); onSelect(iv); }}
                        title={iv.title}
                      >
                        {iv.candidateName}
                      </button>
                    ))}
                    {cell.dayInterviews.length > 3 && (
                      <span className="iv-calendar__event-more">+{cell.dayInterviews.length - 3}</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Week view */}
      {view === "week" && (
        <div className="iv-calendar__week">
          {weekDays.map((cell, idx) => (
            <div
              key={idx}
              className={`iv-calendar__week-day ${cell.isToday ? "iv-calendar__week-day--today" : ""}`}
              onClick={() => onCreate(cell.date)}
            >
              <div className="iv-calendar__week-day-head">
                <span>{dayNames[idx]}</span>
                <b>{cell.date.getDate()}</b>
              </div>
              <div className="iv-calendar__week-events">
                {cell.dayInterviews.map((iv) => (
                  <button
                    key={iv.id}
                    className="iv-calendar__event iv-calendar__event--week"
                    style={{ borderLeftColor: statusColors[iv.status] || "#666" }}
                    onClick={(e) => { e.stopPropagation(); onSelect(iv); }}
                  >
                    <small>{new Date(iv.startsAt).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false })}</small>
                    <span>{iv.candidateName}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Day view */}
      {view === "day" && (
        <div className="iv-calendar__day">
          {dayHours.map(({ hour, interviews: hourInterviews }) => (
            <div key={hour} className={`iv-calendar__day-hour ${hourInterviews.length ? "iv-calendar__day-hour--busy" : ""}`}>
              <span className="iv-calendar__day-hour-label">{String(hour).padStart(2, "0")}:00</span>
              <div className="iv-calendar__day-hour-slot">
                {hourInterviews.map((iv) => (
                  <button
                    key={iv.id}
                    className="iv-calendar__event iv-calendar__event--day"
                    style={{ borderLeftColor: statusColors[iv.status] || "#666" }}
                    onClick={() => onSelect(iv)}
                  >
                    <b>{new Date(iv.startsAt).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false })} — {new Date(iv.endsAt).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false })}</b>
                    <span>{iv.candidateName} · {iv.title}</span>
                    <small>{(iv.interviewers || []).join("、")}</small>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
