import type { ReactNode } from "react";

type Props = {
  eyebrow: string;
  title: string;
  sticky?: boolean;
  children?: ReactNode;
};

export default function JobSectionHeader({
  eyebrow,
  title,
  sticky = false,
  children,
}: Props) {
  return (
    <div
      className={`all-jobs-section__heading${sticky ? " job-section-header--sticky" : ""}`}
    >
      <div>
        <p className="home-section__head-label">{eyebrow}</p>
        <h2 className="home-section__head-title">{title}</h2>
      </div>
      {children && (
        <div className="job-section-header__actions">{children}</div>
      )}
    </div>
  );
}
