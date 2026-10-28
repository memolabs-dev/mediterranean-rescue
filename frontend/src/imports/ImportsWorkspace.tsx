import { useI18n } from "../i18n/I18nProvider";
import { matchRoute, useLocation } from "../router";
import { WorkspaceShell } from "../workspace/WorkspaceShell";
import { ImportList } from "./ImportList";
import { ImportView } from "./ImportView";
import { NewImport } from "./NewImport";
import { DIAGNOSTIC_PATH, IMPORTS_PATH, NEW_PATH } from "./paths";

export { issueText, localDay, sheetLabel } from "./helpers";
export { IMPORTS_PATH } from "./paths";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Parcours A: imports list, W02 (add an export), W03 (what the file holds, before and after saving).
export function ImportsWorkspace() {
  const { t } = useI18n();
  const { pathname } = useLocation();
  const detail = matchRoute(`${IMPORTS_PATH}/:id`, pathname);
  return (
    <WorkspaceShell section="imports" title={t("imports.title")}>
      {(me) =>
        pathname === NEW_PATH || pathname === DIAGNOSTIC_PATH ? (
          // Same element for both steps, so the chosen file survives the change of address.
          <NewImport me={me} step={pathname === DIAGNOSTIC_PATH ? "diagnostic" : "form"} />
        ) : detail?.id && UUID.test(detail.id) ? (
          <ImportView id={detail.id} me={me} />
        ) : (
          <ImportList me={me} />
        )
      }
    </WorkspaceShell>
  );
}

