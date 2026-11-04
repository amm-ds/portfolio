import { useState, type FormEvent, type ReactNode } from "react";
import { CONTACT_EMAIL, LINKEDIN_URL, SITE_TITLE_SUFFIX, SITE_URL } from "../config";
import { EmailIcon, GitHubIcon, LinkedInIcon, PhoneIcon } from "./channelIcons";

/** Direct line — revealed only after the visitor unlocks it in-page. */
export const PHONE_DISPLAY = "+34 670 881 697";
export const PHONE_HREF = "tel:+34670881697";

/** localStorage flag that marks the phone card as unlocked. */
export const PHONE_UNLOCK_KEY = "channel-phone-unlocked";

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

function readUnlockedFlag(): boolean {
  try {
    return localStorage.getItem(PHONE_UNLOCK_KEY) === "1";
  } catch {
    return false;
  }
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

/** The phone card renders locked until the visitor shares an email or phone
 * number; the flag lives only in this browser's localStorage — nothing is
 * sent anywhere. */
function PhoneChannelCard() {
  const [unlocked, setUnlocked] = useState(readUnlockedFlag);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (unlocked) {
    return channelCard({
      name: "Phone",
      address: PHONE_DISPLAY,
      href: PHONE_HREF,
      icon: <PhoneIcon />,
    });
  }

  const onSubmit = (ev: FormEvent) => {
    ev.preventDefault();
    if (!isEmailOrPhone(value)) {
      setError("enter a valid email address or phone number");
      return;
    }
    try {
      localStorage.setItem(PHONE_UNLOCK_KEY, "1");
    } catch {
      // storage unavailable (private mode) — unlocked for this session only
    }
    setUnlocked(true);
  };

  return (
    <div className="channel-card channel-card--locked">
      <span className="channel-icon">
        <PhoneIcon />
      </span>
      <div className="channel-text">
        <span className="channel-name">Phone</span>
        <p className="channel-lock-note">Share your email or phone to unlock the direct line.</p>
        <form className="channel-unlock" onSubmit={onSubmit} noValidate>
          <label className="channel-unlock-label" htmlFor="channel-phone-unlock">
            email or phone
          </label>
          <div className="channel-unlock-row">
            <input
              id="channel-phone-unlock"
              name="phone-unlock"
              type="text"
              autoComplete="off"
              placeholder="you@company.com or +34 …"
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                if (error) setError(null);
              }}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "channel-phone-unlock-error" : undefined}
            />
            <button type="submit">unlock</button>
          </div>
        </form>
        {error && (
          <p className="form-error" id="channel-phone-unlock-error" role="alert">
            {error}
          </p>
        )}
        <p className="channel-unlock-note">
          your email or phone is not stored or sent anywhere — it only unlocks the number on this
          device.
        </p>
      </div>
    </div>
  );
}

/** The shared contact-channel grid — one card per channel, identical on the
 * Contact and About pages. Phone, Email, GitHub, LinkedIn. */
export function ChannelCards() {
  return (
    <div className="channel-grid channel-grid--4">
      <PhoneChannelCard />
      {OPEN_CHANNELS.map(channelCard)}
    </div>
  );
}
