import type { GridMovePreview } from "../../lib/boardPlacement";
import type { Size } from "./workspaceTypes";

interface Props {
  preview: GridMovePreview | null;
  size: Size | null;
}

export default function GridDropPreview({ preview, size }: Props) {
  if (!preview || !size) return null;

  return (
    <div
      className={`grid-drop-preview${preview.willPush ? " grid-drop-preview-push" : ""}${
        preview.canPlace ? "" : " grid-drop-preview-blocked"
      }`}
      style={{
        left: preview.landing.x,
        top: preview.landing.y,
        width: size.width,
        height: size.height,
      }}
      aria-hidden="true"
    />
  );
}
