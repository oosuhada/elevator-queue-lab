import type { ReactNode } from "react";


interface InspectorProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
}

export function Inspector({ title, subtitle, children }: InspectorProps) {
  return (
    <div className="inspector">
      <header>
        <span>Inspector</span>
        <strong>{title}</strong>
        {subtitle ? <small>{subtitle}</small> : null}
      </header>
      <div className="inspector-body">{children}</div>
    </div>
  );
}
