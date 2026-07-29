import type { InputHTMLAttributes } from "react";

/**
 * Shared class string for text/number inputs. Exported so `<select>`
 * elements (which can't render through the `Input` component itself, since
 * it renders a real `<input>`) can reuse the exact same visual styling.
 */
export const inputClasses =
  "w-full rounded border border-gray-300 px-3 py-2 text-sm disabled:cursor-not-allowed disabled:bg-gray-100";

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

/** Shared input primitive for text/number/password/etc. fields. */
export default function Input({ className = "", ...props }: InputProps) {
  return <input className={`${inputClasses} ${className}`.trim()} {...props} />;
}
