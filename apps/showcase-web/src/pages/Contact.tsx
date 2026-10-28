import { Link } from "react-router-dom";
import { Card } from "../components/Card";
import { usePageMeta } from "../seo";
import {
  AVAILABILITY,
  CONTACT_EMAIL,
  LINKEDIN_URL,
  REPO_URL,
  SITE_TITLE_SUFFIX,
  SITE_URL,
} from "../config";

/** Stated concretely as text; Europe/Madrid per project convention. */
const TIMEZONE_LABEL = "Europe/Madrid (CET, UTC+1)";

const mailSubject = `Project inquiry — ${SITE_TITLE_SUFFIX}`;
const mailBody = [
  "Hi,",
  "",
  "I'd like to discuss a project.",
  "",
  "Problem:",
  "Data available:",
  "Timeline:",
  "",
  `— sent from ${SITE_URL}`,
].join("\n");

const mailtoHref = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(
  mailSubject,
)}&body=${encodeURIComponent(mailBody)}`;

const ctaButtonStyle: React.CSSProperties = {
  display: "inline-block",
  background: "var(--accent)",
  color: "#042f2e",
  borderRadius: "var(--radius)",
  padding: "0.65rem 1.4rem",
  fontSize: "0.9rem",
  fontWeight: 700,
  letterSpacing: "0.02em",
  textDecoration: "none",
};

export function Contact() {
  usePageMeta({
    title: "Contact",
    description:
      "Start a conversation about freelance or consulting engagements — problem, data and timeline.",
    canonical: "/contact",
  });

  return (
    <>
      <section className="services-hero">
        <p className="kicker">$ contact</p>
        <h1>Get in touch</h1>
        <p className="contact-status">{AVAILABILITY.status}</p>
      </section>

      <Card className="contact-block">
        <p>
          <a href={mailtoHref} style={ctaButtonStyle}>
            Start a conversation
          </a>
        </p>
        <ul>
          <li>
            GitHub:{" "}
            <a href={`${REPO_URL}/issues`} target="_blank" rel="noopener noreferrer">
              open an issue
            </a>{" "}
            — secondary channel, public by default.
          </li>
          <li>
            LinkedIn:{" "}
            <a
              className="chip-link"
              href={LINKEDIN_URL}
              target="_blank"
              rel="noopener noreferrer"
            >
              linkedin/in/alejandro-mérida-maroto
            </a>
          </li>
          <li>
            Email: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> — the mailto button
            above pre-fills a short brief.
          </li>
          <li>Languages: English, Spanish.</li>
          <li>
            Timezone: {TIMEZONE_LABEL} — replies within {AVAILABILITY.replyHours} hours on
            business days.
          </li>
        </ul>
      </Card>

      <h2 className="section-title">how engagements start</h2>
      <p className="section-intro">
        A free 30–45 minute discovery call: problem, data reality, constraints, and what
        "done" must look like — followed by a written summary with options and rough scope.
        Fixed-scope pilots come after that.{" "}
        <Link to="/services">see services &amp; process →</Link>
      </p>

      <Card className="cta-band">
        <p className="cta-links">
          <Link to="/projects">/projects</Link> ·{" "}
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
            github
          </a>{" "}
          ·{" "}
          <a href={mailtoHref}>email</a>
        </p>
      </Card>
    </>
  );
}
