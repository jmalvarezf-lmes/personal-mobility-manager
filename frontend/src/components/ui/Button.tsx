import type { AnchorHTMLAttributes, ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "danger";
export type ButtonSize = "sm" | "md";

const BASE_CLASSES =
  "inline-flex items-center justify-center whitespace-nowrap rounded font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-brand-blue text-white hover:opacity-90",
  secondary: "bg-gray-100 text-gray-700 hover:bg-gray-200",
  danger: "bg-red-100 text-red-700 hover:bg-red-200",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "px-3 py-1 text-sm",
  md: "px-4 py-2 text-sm",
};

interface ButtonOwnProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
}

/**
 * Builds the same visual classes `Button` renders with, for cases that need
 * button styling on an element `Button` can't render as (e.g. React Router's
 * `Link`, for client-side navigation instead of a full page reload).
 */
export function buttonClasses(
  variant: ButtonVariant = "primary",
  size: ButtonSize = "md",
  className = "",
): string {
  return `${BASE_CLASSES} ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`.trim();
}

type ButtonAsButtonProps = ButtonOwnProps &
  ButtonHTMLAttributes<HTMLButtonElement> & {
    as?: "button";
  };

type ButtonAsAnchorProps = ButtonOwnProps &
  AnchorHTMLAttributes<HTMLAnchorElement> & {
    as: "a";
  };

export type ButtonProps = ButtonAsButtonProps | ButtonAsAnchorProps;

/**
 * Shared button primitive. Renders a `<button>` by default, or an `<a>`
 * when `as="a"` (e.g. the Google login link, which is a real navigation,
 * not a JS action) — both share the same visual variants/sizes so
 * button-styled links and real buttons stay visually identical.
 */
export default function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ButtonProps) {
  const classes = buttonClasses(variant, size, className);

  if (props.as === "a") {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars -- `as` is only a rendering hint, not a valid `<a>` attribute
    const { as, ...anchorProps } = props;
    return <a className={classes} {...anchorProps} />;
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- `as` is only a rendering hint, not a valid `<button>` attribute
  const { as, type, ...buttonProps } = props as ButtonAsButtonProps;
  return <button type={type ?? "button"} className={classes} {...buttonProps} />;
}
