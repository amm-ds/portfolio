import { Card } from "./Card";
import { AVAILABILITY } from "../config";

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

/** Languages, timezone, and reply window — three shared fact cards for the
 * Contact and About pages: the values only, centered, terminal mono type. */
export function LanguagesAvailability() {
  return (
    <div className="facts-grid">
      <Card className="languages-card">
        <p className="languages-line">
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
          <strong>Europe/Madrid (CET, UTC+1)</strong>
        </p>
      </Card>
      <Card className="replies-card">
        <p className="languages-line">
          <strong>within {AVAILABILITY.replyHours}h on business days</strong>
        </p>
      </Card>
    </div>
  );
}
