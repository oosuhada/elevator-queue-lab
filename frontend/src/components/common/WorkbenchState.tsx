import type { ReactNode } from "react";


interface WorkbenchStateProps {
  kind: "loading" | "empty" | "error" | "warning";
  title: string;
  children?: ReactNode;
}

export function WorkbenchState({ kind, title, children }: WorkbenchStateProps) {
  return (
    <div className={`workbench-state workbench-state-${kind}`} role={kind === "error" ? "alert" : "status"}>
      <strong>{title}</strong>
      {children ? <div>{children}</div> : null}
    </div>
  );
}
