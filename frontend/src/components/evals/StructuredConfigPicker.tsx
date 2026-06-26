import { StructuredEvalTarget } from "../../lib/evalCatalog";

interface Props {
  catalog: readonly StructuredEvalTarget[];
  selectedIds: readonly string[];
  onToggle: (catalogId: string) => void;
}

export default function StructuredConfigPicker({
  catalog,
  selectedIds,
  onToggle,
}: Props) {
  if (catalog.length <= 1) {
    return null;
  }

  return (
    <div className="eval-config-picker" role="group" aria-label="Configurations to compare">
      <span className="eval-config-picker-label">Compare</span>
      {catalog.map((item) => {
        const selected = selectedIds.includes(item.catalogId);
        return (
          <button
            type="button"
            key={item.catalogId}
            className={`eval-config-pill${selected ? " selected" : ""}`}
            aria-pressed={selected}
            title={item.target.collectionName}
            onClick={() => onToggle(item.catalogId)}
          >
            {item.shortLabel}
          </button>
        );
      })}
    </div>
  );
}
