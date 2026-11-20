import { cn } from "@/lib/utils";

/**
 * The Instructor's Markdown, rendered to HTML on the server from the content
 * file, with raw HTML disabled: the only HTML here is what Markdown produces.
 */
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

/** The text of server-rendered HTML, e.g. a field's label for screen readers. */
export function plainText(html: string): string {
  return (
    new DOMParser().parseFromString(html, "text/html").body.textContent ?? ""
  ).trim();
}
