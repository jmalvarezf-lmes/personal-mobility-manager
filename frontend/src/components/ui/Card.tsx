import type { HTMLAttributes } from "react";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Set to false to omit the standard padding, e.g. for a full-bleed image header. Defaults to true. */
  padded?: boolean;
}

/** Shared card primitive: white surface, subtle border/shadow, standard padding. */
export default function Card({ className = "", padded = true, ...props }: CardProps) {
  return (
    <div
      className={`rounded border border-gray-200 bg-white shadow-sm ${padded ? "p-4" : ""} ${className}`.trim()}
      {...props}
    />
  );
}
