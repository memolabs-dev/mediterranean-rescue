import { Fieldset } from "@base-ui/react/fieldset";
import { Radio } from "@base-ui/react/radio";
import { RadioGroup } from "@base-ui/react/radio-group";
import type { ReactNode } from "react";
import { useI18n } from "../i18n/I18nProvider";

export interface Facet<V extends string> {
  value: V;
  label: string;
  count: number;
}

export interface FilterBarProps<V extends string> {
  legend: string;
  facets: readonly Facet<V>[];
  value: V;
  onValueChange: (value: V) => void;
  /** Other criteria (selects, period) placed after the facets. */
  children?: ReactNode;
}

// Exclusive facets applied immediately, each with its server count (FilterBar contract).
export function FilterBar<V extends string>({ legend, facets, value, onValueChange, children }: FilterBarProps<V>) {
  const { number } = useI18n();
  return (
    <div className="ui-filter-bar">
      <Fieldset.Root
        render={<RadioGroup value={value} onValueChange={(next) => onValueChange(next as V)} />}
        className="ui-facets"
      >
        <Fieldset.Legend className="ui-field__label">{legend}</Fieldset.Legend>
        <div className="ui-facets__row">
          {facets.map((facet) => (
            <Radio.Root key={facet.value} value={facet.value} className="ui-facet">
              <span>{facet.label}</span>{" "}
              <span className="ui-facet__count">{number(facet.count)}</span>
            </Radio.Root>
          ))}
        </div>
      </Fieldset.Root>
      {children}
    </div>
  );
}
