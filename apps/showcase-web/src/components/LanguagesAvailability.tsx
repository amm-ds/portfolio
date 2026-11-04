import { Card } from "./Card";
import { AVAILABILITY } from "../config";

/** Stated concretely as text; Europe/Madrid per project convention. */
const TIMEZONE_LABEL = "Europe/Madrid (CET, UTC+1)";

/** Languages & availability — one shared card for the Contact and About
 * pages. Catalan renders as an explicit text chip: it has no unambiguous
 * country flag, so it gets a label instead of an emoji. */
export function LanguagesAvailability() {
  return (
    <Card className="languages-card">
      <p className="languages-line">
        <strong>Languages:</strong> <span className="language-item">🇬🇧 English</span> ·{" "}
        <span className="language-item">🇪🇸 Spanish</span> ·{" "}
        <span className="chip languages-chip">Catalan</span>
      </p>
      <p className="languages-line">
        <strong>{TIMEZONE_LABEL}</strong> — replies within {AVAILABILITY.replyHours}h on business
        days.
      </p>
    </Card>
  );
}
