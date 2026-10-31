import { useState, type FormEvent } from "react";
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

export interface InquiryFields {
  name: string;
  email: string;
  organization: string;
  message: string;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_MESSAGE = 20;

export function validateInquiry(fields: InquiryFields): Partial<Record<keyof InquiryFields, string>> {
  const errors: Partial<Record<keyof InquiryFields, string>> = {};
  if (!fields.name.trim()) errors.name = "name is required";
  if (!fields.email.trim()) errors.email = "email is required";
  else if (!EMAIL_RE.test(fields.email.trim())) errors.email = "enter a valid email address";
  if (!fields.message.trim()) errors.message = "message is required";
  else if (fields.message.trim().length < MIN_MESSAGE)
    errors.message = `message must be at least ${MIN_MESSAGE} characters`;
  return errors;
}

/** The mailto the form composes on submit — pure so tests can check it exactly. */
export function buildInquiryMailto(fields: InquiryFields): string {
  const subject = `Project inquiry — ${fields.organization.trim() || fields.name.trim()}`;
  const body = [
    `Name: ${fields.name.trim()}`,
    `Email: ${fields.email.trim()}`,
    `Organization: ${fields.organization.trim() || "—"}`,
    "",
    "Message:",
    fields.message.trim(),
    "",
    `— sent from ${SITE_URL}`,
  ].join("\n");
  return `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

export function Contact() {
  usePageMeta({
    title: "Contact",
    description:
      "Start a conversation about freelance or consulting engagements — problem, data and timeline.",
    canonical: "/contact",
  });

  const [fields, setFields] = useState<InquiryFields>({
    name: "",
    email: "",
    organization: "",
    message: "",
  });
  const [errors, setErrors] = useState<Partial<Record<keyof InquiryFields, string>>>({});
  const [sent, setSent] = useState(false);

  const setField = (key: keyof InquiryFields) => (value: string) => {
    setFields((f) => ({ ...f, [key]: value }));
    setErrors((e) => (e[key] ? { ...e, [key]: undefined } : e));
    setSent(false);
  };

  const onSubmit = (ev: FormEvent) => {
    ev.preventDefault();
    const nextErrors = validateInquiry(fields);
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;
    window.location.href = buildInquiryMailto(fields);
    setSent(true);
  };

  const fieldProps = (key: keyof InquiryFields) => ({
    "aria-invalid": errors[key] ? true : undefined,
    "aria-describedby": errors[key] ? `contact-${key}-error` : undefined,
  });

  return (
    <>
      <section className="services-hero">
        <p className="kicker">$ contact</p>
        <h1>Get in touch</h1>
        <p className="contact-status">{AVAILABILITY.status}</p>
      </section>

      <form className="contact-form" onSubmit={onSubmit} noValidate>
        <div className="form-field">
          <label htmlFor="contact-name">name *</label>
          <input
            id="contact-name"
            name="name"
            type="text"
            autoComplete="name"
            value={fields.name}
            onChange={(e) => setField("name")(e.target.value)}
            {...fieldProps("name")}
          />
          {errors.name && (
            <p className="form-error" id="contact-name-error">
              {errors.name}
            </p>
          )}
        </div>
        <div className="form-field">
          <label htmlFor="contact-email">email *</label>
          <input
            id="contact-email"
            name="email"
            type="email"
            autoComplete="email"
            value={fields.email}
            onChange={(e) => setField("email")(e.target.value)}
            {...fieldProps("email")}
          />
          {errors.email && (
            <p className="form-error" id="contact-email-error">
              {errors.email}
            </p>
          )}
        </div>
        <div className="form-field">
          <label htmlFor="contact-organization">organization</label>
          <input
            id="contact-organization"
            name="organization"
            type="text"
            autoComplete="organization"
            value={fields.organization}
            onChange={(e) => setField("organization")(e.target.value)}
          />
        </div>
        <div className="form-field">
          <label htmlFor="contact-message">message *</label>
          <textarea
            id="contact-message"
            name="message"
            rows={6}
            value={fields.message}
            onChange={(e) => setField("message")(e.target.value)}
            {...fieldProps("message")}
          />
          {errors.message && (
            <p className="form-error" id="contact-message-error">
              {errors.message}
            </p>
          )}
        </div>
        <div className="form-actions">
          <button type="submit">send inquiry</button>
          <p className="form-note">
            submitting opens your mail client with the message pre-filled — nothing is stored or
            sent from this site.
          </p>
        </div>
        {sent && (
          <p className="form-note form-sent" role="status">
            your mail client should have opened with the message pre-filled — hit send there to
            deliver it to {CONTACT_EMAIL}.
          </p>
        )}
      </form>

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
          · <a href={mailtoHref}>email</a>
        </p>
      </Card>
    </>
  );
}
