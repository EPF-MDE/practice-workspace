import { useEffect, useRef } from "react";
import {
  type Editor,
  getSnapshot,
  type TLEditorSnapshot,
  type TLStoreSnapshot,
  Tldraw,
} from "tldraw";
import "tldraw/tldraw.css";

/**
 * tldraw, loaded only on a page with a drawing step (it is most of the
 * bundle). Locally and in Playwright it runs in development mode and needs no
 * key; on production the hobby key comes from the app's settings.
 */

export type Snapshot = Partial<TLEditorSnapshot> | TLStoreSnapshot;

/** An Example or Reference Drawing: a read-only canvas, fitted to its shapes. */
export function ReadOnlyDrawing({
  snapshot,
  licenseKey,
}: {
  snapshot: Snapshot;
  licenseKey: string;
}) {
  return (
    <Tldraw
      snapshot={snapshot as TLEditorSnapshot}
      licenseKey={licenseKey || undefined}
      hideUi
      onMount={(editor) => {
        editor.updateInstanceState({ isReadonly: true });
        editor.zoomToFit();
      }}
    />
  );
}

/**
 * Hands the snapshot to `onChange` 300 ms after the Student's last change, and
 * at once when the page goes away. Returns what stops it.
 */
function keepEveryChange(
  mounted: Editor,
  onChange: (snapshot: TLEditorSnapshot) => void
) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const save = () => {
    timer = undefined;
    onChange(getSnapshot(mounted.store));
  };
  const stop = mounted.store.listen(
    () => {
      clearTimeout(timer);
      timer = setTimeout(save, 300);
    },
    { source: "user", scope: "document" }
  );
  const flush = () => {
    if (timer !== undefined) {
      clearTimeout(timer);
      save();
    }
  };
  window.addEventListener("pagehide", flush);
  return () => {
    flush();
    window.removeEventListener("pagehide", flush);
    stop();
  };
}

/**
 * The Student's canvas. Every change to the drawing reaches `onChange` (the
 * page keeps it in localStorage, never in the Store); `onEditor` hands the
 * editor to the send button.
 */
export function EditableDrawing({
  initial,
  licenseKey,
  readOnly,
  onChange,
  onEditor,
}: {
  initial: Snapshot | null;
  licenseKey: string;
  readOnly: boolean;
  onChange: (snapshot: TLEditorSnapshot) => void;
  onEditor: (editor: Editor) => void;
}) {
  const editor = useRef<Editor | null>(null);
  useEffect(() => {
    editor.current?.updateInstanceState({ isReadonly: readOnly });
  }, [readOnly]);
  return (
    <Tldraw
      snapshot={(initial ?? undefined) as TLEditorSnapshot | undefined}
      licenseKey={licenseKey || undefined}
      onMount={(mounted) => {
        editor.current = mounted;
        onEditor(mounted);
        mounted.updateInstanceState({ isReadonly: readOnly });
        if (initial) mounted.zoomToFit();
        return keepEveryChange(mounted, onChange);
      }}
    />
  );
}

/** The drawing as sent: the PNG tldraw exports, in base64, and the snapshot. */
export async function exportDrawing(
  editor: Editor
): Promise<{ png_base64: string; snapshot: TLEditorSnapshot } | null> {
  const shapes = [...editor.getCurrentPageShapeIds()];
  if (shapes.length === 0) return null;
  const { blob } = await editor.toImage(shapes, {
    format: "png",
    background: true,
  });
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000)
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return { png_base64: btoa(binary), snapshot: getSnapshot(editor.store) };
}
