/**
 * One in-flight upload row: filename + stage label + indeterminate shimmer.
 *
 * Visual states map 1:1 to ``UploadJob.stage``:
 *  - "uploading" : "Uploading..." (shimmer)
 *  - "indexing"  : "Indexing..."  (shimmer)
 *  - "error"     : error text + Retry button
 *
 * No "ready" state — once ingestion succeeds the row is removed by the
 * parent and the doc joins the indexed list.
 */

export type UploadStage = "uploading" | "indexing" | "error";

interface Props {
  name: string;
  stage: UploadStage;
  error?: string | null;
  onRetry?: () => void;
}

const STAGE_LABEL: Record<UploadStage, string> = {
  uploading: "Uploading...",
  indexing: "Indexing...",
  error: "Failed",
};

export default function ProgressRow({ name, stage, error, onRetry }: Props) {
  const isError = stage === "error";
  return (
    <li className={`progress-row ${stage}`}>
      <div className="progress-row-head">
        <span className="progress-row-name">{name}</span>
        <span className="progress-row-stage">{STAGE_LABEL[stage]}</span>
      </div>
      {isError ? (
        <div className="progress-row-error">
          <span>{error ?? "Something went wrong."}</span>
          {onRetry && (
            <button className="retry" onClick={onRetry}>
              Retry
            </button>
          )}
        </div>
      ) : (
        <div className="progress-bar">
          <span className="progress-bar-fill" />
        </div>
      )}
    </li>
  );
}
