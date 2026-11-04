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
 * Contact and About pages: the values only, centered, terminal mono type in
 * the same grey as body text. */
export function LanguagesAvailability() {
  return (
    <div className="facts-grid">
      <Card className="languages-card">
        <p className="languages-line">
          <span className="language-item">🇬🇧 English</span> ·{" "}
          <span className="language-item">🇪🇸 Spanish</span> ·{" "}
          <span className="language-item">
            <SenyeraFlag />
            Catalan
          </span>
        </p>
      </Card>
      <Card className="timezone-card">
        <p className="languages-line">
          <span className="fact-symbol" aria-hidden="true">
            🌍
          </span>{" "}
          Europe/Madrid (CET, UTC+1)
        </p>
      </Card>
      <Card className="replies-card">
        <p className="languages-line">
          <span className="fact-symbol" aria-hidden="true">
            💬
          </span>{" "}
          replies within {AVAILABILITY.replyHours}h on business days
        </p>
      </Card>
    </div>
  );
}
