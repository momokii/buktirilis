import { Button, TextInput } from "../ui";

export function StringListField({
  id,
  label,
  hint,
  values,
  onChange,
  addLabel,
  placeholder,
}: {
  id: string;
  label: string;
  hint?: string;
  values: string[];
  onChange: (values: string[]) => void;
  addLabel: string;
  placeholder?: string;
}) {
  const update = (index: number, value: string) => {
    onChange(values.map((item, itemIndex) => (itemIndex === index ? value : item)));
  };
  return (
    <fieldset className="list-field">
      <legend>{label}</legend>
      {hint ? <p className="field-hint">{hint}</p> : null}
      {values.length === 0 ? <p className="muted small">None added.</p> : null}
      <div className="list-field-rows">
        {values.map((value, index) => (
          <div className="list-field-row" key={`${id}-${index}`}>
            <TextInput
              id={`${id}-${index}`}
              aria-label={`${label} ${index + 1}`}
              value={value}
              placeholder={placeholder}
              onChange={(event) => update(index, event.target.value)}
            />
            <Button
              type="button"
              size="sm"
              aria-label={`Remove ${label} ${index + 1}`}
              onClick={() => onChange(values.filter((_, itemIndex) => itemIndex !== index))}
            >
              Remove
            </Button>
          </div>
        ))}
      </div>
      <Button
        type="button"
        size="sm"
        variant="secondary"
        onClick={() => onChange([...values, ""])}
      >
        {addLabel}
      </Button>
    </fieldset>
  );
}
