import { useState, useEffect, useCallback } from "react";
import CompetitionRoleEvolution from "./CompetitionRoleEvolution";
import CompetitionEvidence from "./CompetitionEvidence";
import JobSectionHeader from "./JobSectionHeader";

type RoleWorkspaceView = "evolution" | "verification";

export default function CompetitionRoleWorkspace() {
  const [activeView, setActiveView] = useState<RoleWorkspaceView>(() => {
    const saved = sessionStorage.getItem("talentmatch-role-workspace-view");
    if (saved === "verification" || saved === "evolution") {
      return saved as RoleWorkspaceView;
    }
    return "evolution";
  });

  const [selectedRoleId, setSelectedRoleId] = useState("java-developer");

  useEffect(() => {
    sessionStorage.setItem("talentmatch-role-workspace-view", activeView);
  }, [activeView]);

  const switchTo = useCallback((view: RoleWorkspaceView) => {
    setActiveView(view);
  }, []);

  const subtitle =
    activeView === "evolution"
      ? "了解岗位要求在不同时间发生的变化，及时调整招聘标准和职位描述。"
      : "检查职位要求是否有招聘数据支持，减少不合理或缺少依据的招聘要求。";

  return (
    <div className="comp-role-workspace">
      <JobSectionHeader
        eyebrow="ROLE CAPABILITY MANAGEMENT"
        title="岗位能力管理"
      >
        <div
          className="comp-role-workspace__tabs"
          role="tablist"
          aria-label="岗位能力工具"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activeView === "evolution"}
            className={`comp-role-workspace__tab${activeView === "evolution" ? " comp-role-workspace__tab--active" : ""}`}
            onClick={() => switchTo("evolution")}
          >
            岗位能力变化
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeView === "verification"}
            className={`comp-role-workspace__tab${activeView === "verification" ? " comp-role-workspace__tab--active" : ""}`}
            onClick={() => switchTo("verification")}
          >
            岗位要求核验
          </button>
        </div>
      </JobSectionHeader>

      {/* ── Subtitle ── */}
      <p className="comp-role-workspace__subtitle">{subtitle}</p>

      {/* ── Tab panels ── */}
      <div role="tabpanel" className="comp-role-workspace__panel">
        {activeView === "evolution" ? (
          <CompetitionRoleEvolution
            embedded
            roleId={selectedRoleId}
            onRoleChange={setSelectedRoleId}
          />
        ) : (
          <CompetitionEvidence
            embedded
            roleId={selectedRoleId}
            onRoleChange={setSelectedRoleId}
          />
        )}
      </div>
    </div>
  );
}
