import { Field } from "@base-ui/react/field";
import type { ComponentProps } from "react";
import { useI18n } from "../i18n/I18nProvider";

export interface TextFieldProps extends Omit<ComponentProps<typeof Field.Control>, "children"> {
  label: string;
  description?: string;
  /**
   * Error to show next to the field; the field is invalid while it is set. Callers show it
   * after blur or submission, never on arrival in an empty field (TextField contract).
   */
  error?: string | null;
  /** Shows "optional" in the label; required fields are the default in review forms. */
  optional?: boolean;
}

export function TextField({ label, description, error, optional, className, ...props }: TextFieldProps) {
  const { t } = useI18n();
  return (
    <Field.Root className={["ui-field", className].filter(Boolean).join(" ")} invalid={Boolean(error)}>
      <Field.Label className="ui-field__label">
        {label}
        {optional && <span className="ui-field__hint"> ({t("ui.optional")})</span>}
      </Field.Label>
      {/* aria-required rather than required: errors come from the form flow, not browser bubbles. */}
      <Field.Control {...props} aria-required={!optional || undefined} className="ui-field__control" />
      {description && <Field.Description className="ui-field__description">{description}</Field.Description>}
      {error && (
        <Field.Error className="ui-field__error" match>
          {error}
        </Field.Error>
      )}
    </Field.Root>
  );
}
