import { cn } from "@/lib/utils";

export function Html({
  html,
  className,
}: {
  html: string;
  className?: string;
}) {
  return (
    <div
      className={cn("content", className)}
      // oxlint-disable-next-line react/no-danger -- the back end renders it with markdown-it, raw HTML disabled, so it holds only what Markdown produces
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

export function plainText(html: string): string {
  return (
    new DOMParser().parseFromString(html, "text/html").body.textContent ?? ""
  ).trim();
}
