import { useState, type FormEvent, type ReactNode } from "react";
import { unlockContactPhone } from "../api";
import { CONTACT_EMAIL, LINKEDIN_URL, SITE_TITLE_SUFFIX, SITE_URL } from "../config";
import { EmailIcon, GitHubIcon, LinkedInIcon, PhoneIcon } from "./channelIcons";

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

/** The Email card's mailto, prefilled with the inquiry scaffold. Also used by
 * the Contact page's footer link. */
export const channelMailtoHref = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(
  mailSubject,
)}&body=${encodeURIComponent(mailBody)}`;

/** Validation for the phone unlock gate — an email address or a phone number.
 * Exported so tests can check the regexes directly. */
export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const PHONE_RE = /^\+?[0-9][0-9\s().-]{5,18}[0-9]$/;

export function isEmailOrPhone(value: string): boolean {
  const v = value.trim();
  return EMAIL_RE.test(v) || PHONE_RE.test(v);
}

/** The unlocked card is a plain tel link built from the number the API
 * returned — the digits never appear in this bundle. */
function telHref(phone: string): string {
  return `tel:${phone.replace(/[^+\d]/g, "")}`;
}

/** The always-open channels — the whole card is the link. The GitHub card
 * points at the profile, not at any single repository. */
const OPEN_CHANNELS: { name: string; address: string; href: string; icon: ReactNode }[] = [
  {
    name: "Email",
    address: CONTACT_EMAIL,
    href: channelMailtoHref,
    icon: <EmailIcon />,
  },
  {
    name: "GitHub",
    address: "github.com/amm-ds",
    href: "https://github.com/amm-ds",
    icon: <GitHubIcon />,
  },
  {
    name: "LinkedIn",
    address: "linkedin/in/alejandro-mérida-maroto",
    href: LINKEDIN_URL,
    icon: <LinkedInIcon />,
  },
];

function channelCard(ch: (typeof OPEN_CHANNELS)[number]) {
  const external = ch.href.startsWith("http");
  return (
    <a
      key={ch.name}
      className="channel-card"
      href={ch.href}
      target={external ? "_blank" : undefined}
      rel={external ? "noopener noreferrer" : undefined}
    >
      <span className="channel-icon">{ch.icon}</span>
      <span className="channel-text">
        <span className="channel-name">{ch.name}</span>
        <span className="channel-address">{ch.address}</span>
      </span>
    </a>
  );
}

/** The unlocked phone line keeps the gate's slim full-width structure — it
 * replaces the gate in place instead of becoming a fourth grid card. */
function PhoneLinkCard({ phone }: { phone: string }) {
  return (
    <a className="channel-card channel-card--slim" href={telHref(phone)}>
      <span className="channel-icon">
        <PhoneIcon />
      </span>
      <span className="channel-text">
        <span className="channel-name">Phone</span>
        <span className="channel-address">{phone}</span>
      </span>
    </a>
  );
}

/** The phone card renders locked; the number is fetched from the API once the
 * visitor shares an email or phone number. The unlock is view state only —
 * the gate is back on every reload. Submissions (valid or not) are recorded
 * server-side so the owner can see who asked for the line; nothing is stored
 * in the browser. */
function PhoneChannelCard() {
  const [phone, setPhone] = useState<string | null>(null);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (phone) {
    return <PhoneLinkCard phone={phone} />;
  }

  const onSubmit = async (ev: FormEvent) => {
    ev.preventDefault();
    if (!isEmailOrPhone(value)) {
      setError("enter a valid email address or phone number");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await unlockContactPhone(value);
      setValue("");
      setPhone(res.phone);
    } catch {
      setError("couldn't reach the server right now — the email channel below works anytime");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="channel-card channel-card--locked channel-card--slim">
      <span className="channel-icon">
        <PhoneIcon />
      </span>
      <div className="channel-text">
        <span className="channel-name">Phone</span>
        <p className="channel-lock-note">Share your email or phone to unlock.</p>
        <form className="channel-unlock" onSubmit={onSubmit} noValidate>
          <div className="channel-unlock-row">
            <input
              id="channel-phone-unlock"
              name="phone-unlock"
              type="text"
              autoComplete="off"
              placeholder="you@company.com or +34 600 000 000"
              value={value}
              disabled={busy}
              onChange={(e) => {
                setValue(e.target.value);
                if (error) setError(null);
              }}
              aria-label="email or phone"
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "channel-phone-unlock-error" : undefined}
            />
            <button type="submit" disabled={busy}>
              {busy ? "unlocking…" : "unlock"}
            </button>
          </div>
        </form>
        {error && (
          <p className="form-error" id="channel-phone-unlock-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}

/** The shared contact-channel grid — the slim phone gate spans the full row,
 * the three link cards fill the remaining three columns at the same full
 * width as the facts cards below. Identical on Contact and About. */
export function ChannelCards() {
  return (
    <div className="channel-grid">
      <PhoneChannelCard />
      {OPEN_CHANNELS.map(channelCard)}
    </div>
  );
}
