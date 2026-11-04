import { Card } from "./Card";
import { AVAILABILITY } from "../config";

/** Stated concretely as text; Europe/Madrid per project convention. */
const TIMEZONE_LABEL = "Europe/Madrid (CET, UTC+1)";

/** The Senyera — the Catalan flag: four red stripes on a yellow field,
 * drawn as a small inline SVG. Catalan has no unambiguous country emoji, so
 * it never gets one (a wrong-flag emoji would misstate identity). */
function SenyeraFlag() {
  return (
    <svg
      className="flag-senyera"
      viewBox="0 0 27 18"
      width="18"
      height="12"
      aria-hidden="true"
      focusable="false"
    >
      <rect width="27" height="18" fill="#FCDD09" />
      {[2, 6, 10, 14].map((y) => (
        <rect key={y} x="0" y={y} width="27" height="2" fill="#DA121A" />
      ))}
    </svg>
  );
}

/** Languages & timezone — the two shared fact cards for the Contact and
 * About pages: a languages card (English, Spanish, Catalan — the Catalan
 * flag drawn inline) and a timezone & replies card, both with bold labels. */
export function LanguagesAvailability() {
  return (
    <div className="facts-grid">
      <Card className="languages-card">
        <p className="languages-line">
          <strong>Languages:</strong>{" "}
          <strong className="language-item">🇬🇧 English</strong> ·{" "}
          <strong className="language-item">🇪🇸 Spanish</strong> ·{" "}
          <strong className="language-item">
            <SenyeraFlag />
            Catalan
          </strong>
        </p>
      </Card>
      <Card className="timezone-card">
        <p className="languages-line">
          <strong>{TIMEZONE_LABEL}</strong>
        </p>
        <p className="languages-line">
          <strong>replies within {AVAILABILITY.replyHours}h on business days</strong>
        </p>
      </Card>
    </div>
  );
}
