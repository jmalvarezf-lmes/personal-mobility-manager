import type { ReactNode } from "react";

export interface PageHeaderProps {
  title: ReactNode;
  action?: ReactNode;
  className?: string;
}

/** Shared page header: title + optional action slot, replacing the repeated `<h1> + button` pattern. */
export default function PageHeader({ title, action, className = "" }: PageHeaderProps) {
  return (
    <div className={`mb-4 flex items-center justify-between ${className}`.trim()}>
      <h1 className="text-2xl font-bold text-gray-800">{title}</h1>
      {action && <div>{action}</div>}
    </div>
  );
}
