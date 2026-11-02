import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
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

/** Simple-icons-style inline SVGs (24×24, single path, currentColor). */
function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  );
}

function LinkedInIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}

function EmailIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M2 4.5A2.5 2.5 0 0 1 4.5 2h15A2.5 2.5 0 0 1 22 4.5v15a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 19.5v-15zm2.7.5L12 10.35 19.3 5H4.7zM20 6.6l-7.6 6.18a1 1 0 0 1-1.28 0L4 6.6V19h16V6.6z" />
    </svg>
  );
}

/** Contact channels: one card per channel, the whole card is the link. */
const CHANNELS: { name: string; address: string; href: string; icon: ReactNode }[] = [
  {
    name: "GitHub",
    address: "github.com/amm-ds",
    href: `${REPO_URL}/issues`,
    icon: <GitHubIcon />,
  },
  {
    name: "LinkedIn",
    address: "linkedin/in/alejandro-mérida-maroto",
    href: LINKEDIN_URL,
    icon: <LinkedInIcon />,
  },
  {
    name: "Email",
    address: CONTACT_EMAIL,
    href: mailtoHref,
    icon: <EmailIcon />,
  },
];

/** How engagements start — rendered as a numbered roadmap timeline. The
 * revision-round wording deliberately carries no count. */
const START_STEPS = [
  {
    title: "describe",
    text: "You describe the problem, the data and the goal — a short call or an email is enough.",
  },
  {
    title: "proposal",
    text: "You get a scoped proposal: objectives, data needs, deliverables, timeline, fixed price or retainer.",
  },
  {
    title: "pilot",
    text: "A pilot or engagement starts; you see work in a shared repository from day one.",
  },
  {
    title: "delivery",
    text: "Delivery includes structured revision rounds; handover is the full repository, documentation and a walkthrough.",
  },
];

export interface InquiryFields {
  name: string;
  email: string;
  organization: string;
  message: string;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_MESSAGE = 10;

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
        <p className="kicker">&gt; contact</p>
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

      <div className="channel-grid">
        {CHANNELS.map((c) => (
          <a
            key={c.name}
            className="channel-card"
            href={c.href}
            target={c.href.startsWith("http") ? "_blank" : undefined}
            rel={c.href.startsWith("http") ? "noopener noreferrer" : undefined}
          >
            <span className="channel-icon">{c.icon}</span>
            <span className="channel-text">
              <span className="channel-name">{c.name}</span>
              <span className="channel-address">{c.address}</span>
            </span>
          </a>
        ))}
      </div>
      <p className="contact-meta">
        Languages: English, Spanish. · Timezone: {TIMEZONE_LABEL} — replies within{" "}
        {AVAILABILITY.replyHours} hours on business days.
      </p>

      <h2 className="section-title">how engagements start</h2>
      <ol className="start-timeline">
        {START_STEPS.map((s, i) => (
          <li key={s.title}>
            <span className="step-num">{String(i + 1).padStart(2, "0")}</span>
            <h3>{s.title}</h3>
            <p>{s.text}</p>
          </li>
        ))}
      </ol>
      <p className="section-intro">
        <Link to="/services">see services &amp; process →</Link>
      </p>

      <p className="footer-links">
        <Link to="/projects">/projects</Link> ·{" "}
        <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
          github
        </a>{" "}
        · <a href={mailtoHref}>email</a>
      </p>
    </>
  );
}
